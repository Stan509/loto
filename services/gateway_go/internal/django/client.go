package django

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"net/http"
	"time"
)

// Client encapsule les appels HTTP vers l'API Django.
type Client struct {
	baseURL string
	client  *http.Client
}

// NewClient crée un client Django.
func NewClient(baseURL string) *Client {
	return &Client{
		baseURL: baseURL,
		client: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

// ForwardTicketBatch envoie un batch de tickets validés à Django.
func (c *Client) ForwardTicketBatch(ctx context.Context, endpoint string, body []byte, headers map[string]string) ([]byte, int, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+endpoint, bytes.NewReader(body))
	if err != nil {
		return nil, 0, fmt.Errorf("create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	for k, v := range headers {
		req.Header.Set(k, v)
	}

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, 0, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, resp.StatusCode, fmt.Errorf("read body: %w", err)
	}

	return respBody, resp.StatusCode, nil
}
