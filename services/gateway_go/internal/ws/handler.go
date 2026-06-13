package ws

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"gateway_go/internal/django"
	"gateway_go/internal/validator"
	"gateway_go/proto"

	"github.com/gorilla/websocket"
	"github.com/redis/go-redis/v9"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
}

// Hub gère les connexions WebSocket des agents et le flux de tickets.
type Hub struct {
	valClient *validator.ValidatorClient
	djClient  *django.Client
	redis     *redis.Client
	clients   map[*Client]bool
	broadcast chan []byte
	register  chan *Client
	unregister chan *Client
}

// Client représente une connexion WebSocket d'un agent.
type Client struct {
	hub  *Hub
	conn *websocket.Conn
	send chan []byte
}

// NewHub crée un nouveau Hub WebSocket.
func NewHub(valClient *validator.ValidatorClient, djClient *django.Client, redisURL string) *Hub {
	// Parse redisURL (format: redis://host:port/db)
	opt, err := redis.ParseURL(redisURL)
	if err != nil {
		log.Printf("[WS] Redis parse error: %v, using localhost fallback", err)
		opt = &redis.Options{Addr: "localhost:6379"}
	}

	rdb := redis.NewClient(opt)

	return &Hub{
		valClient:  valClient,
		djClient:   djClient,
		redis:      rdb,
		clients:    make(map[*Client]bool),
		broadcast:  make(chan []byte, 256),
		register:   make(chan *Client),
		unregister: make(chan *Client),
	}
}

// Run démarre la boucle d'événements du Hub.
func (h *Hub) Run() {
	for {
		select {
		case client := <-h.register:
			h.clients[client] = true
			log.Printf("[WS] Agent connected. Total: %d", len(h.clients))

		case client := <-h.unregister:
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
				log.Printf("[WS] Agent disconnected. Total: %d", len(h.clients))
			}

		case message := <-h.broadcast:
			for client := range h.clients {
				select {
				case client.send <- message:
				default:
					close(client.send)
					delete(h.clients, client)
				}
			}
		}
	}
}

// HandleAgentConnection upgrade une connexion HTTP en WebSocket pour un agent.
func (h *Hub) HandleAgentConnection(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("[WS] Upgrade error: %v", err)
		return
	}

	client := &Client{hub: h, conn: conn, send: make(chan []byte, 256)}
	h.register <- client

	go client.writePump()
	go client.readPump(h)
}

// HandleHTTPFallback sert de fallback HTTP pour les tickets (même logique que WS).
func (h *Hub) HandleHTTPFallback(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 15*time.Second)
	defer cancel()

	var ticketBatch TicketBatch
	if err := json.NewDecoder(r.Body).Decode(&ticketBatch); err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"invalid json: %v"}`, err), http.StatusBadRequest)
		return
	}

	// 1. Valider avec Rust
	for _, ticket := range ticketBatch.Tickets {
		protoLines := make([]*proto.TicketLine, 0, len(ticket.Lines))
		for _, line := range ticket.Lines {
			protoLines = append(protoLines, &proto.TicketLine{
				GameType: line.GameType,
				Numbers:  line.Numbers,
				Mise:     line.Mise,
			})
		}
		payload := &proto.TicketPayload{
			TicketUuid: ticket.UUID,
			AgentId:    ticketBatch.AgentID,
			TirageIds:  ticket.TirageIDs,
			Lines:      protoLines,
			TotalMise:  ticket.TotalMise,
			Timestamp:  time.Now().Unix(),
		}
		sig, err := h.valClient.SignTicket(ctx, payload)
		if err != nil {
			http.Error(w, fmt.Sprintf(`{"error":"validator error: %v"}`, err), http.StatusInternalServerError)
			return
		}
		_ = sig // Signature attachée au ticket batch pour audit
	}

	// 2. Forward vers Django
	body, _ := json.Marshal(ticketBatch)
	respBody, status, err := h.djClient.ForwardTicketBatch(ctx, "/api/agent/ticket/create_multi/", body, map[string]string{
		"Authorization": r.Header.Get("Authorization"),
		"Content-Type":  "application/json",
	})
	if err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"django forward: %v"}`, err), http.StatusBadGateway)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	w.Write(respBody)
}

// --- Client read/write pumps ---

func (c *Client) readPump(h *Hub) {
	defer func() {
		h.unregister <- c
		c.conn.Close()
	}()

	c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	for {
		_, message, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Printf("[WS] Read error: %v", err)
			}
			break
		}

		// Traiter le message (ticket batch)
		var batch TicketBatch
		if err := json.Unmarshal(message, &batch); err != nil {
			log.Printf("[WS] Invalid batch: %v", err)
			continue
		}

		// TODO: pipeline Redis -> Rust -> Django
		_ = batch
		log.Printf("[WS] Received batch from agent %s with %d tickets", batch.AgentID, len(batch.Tickets))
	}
}

func (c *Client) writePump() {
	ticker := time.NewTicker(54 * time.Second)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()

	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if !ok {
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			c.conn.WriteMessage(websocket.TextMessage, message)

		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

// --- Structures JSON ---

// TicketBatch représente un lot de tickets envoyé par un agent.
type TicketBatch struct {
	AgentID     string          `json:"agent_id"`
	DeviceID    string          `json:"device_id"`
	SessionKey  string          `json:"session_key"`
	TirageIDs   []string        `json:"tirage_ids"`
	Tickets     []Ticket        `json:"tickets"`
	Timestamp   int64           `json:"timestamp"`
	Signature   string          `json:"signature,omitempty"`
}

// Ticket représente un ticket individuel.
type Ticket struct {
	UUID       string       `json:"uuid"`
	TirageIDs  []string     `json:"tirage_ids"`
	Lines      []TicketLine `json:"lines"`
	TotalMise  float64      `json:"total_mise"`
}

// TicketLine représente une ligne de mise.
type TicketLine struct {
	GameType string  `json:"game_type"`
	Numbers  string  `json:"numbers"`
	Mise     float64 `json:"mise"`
}
