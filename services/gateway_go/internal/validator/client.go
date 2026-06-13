package validator

import (
	"context"
	"fmt"

	"gateway_go/proto"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// ValidatorClient encapsule la connexion gRPC au service Rust.
type ValidatorClient struct {
	conn   *grpc.ClientConn
	client proto.ValidatorClient
}

// NewClient crée une connexion au validator Rust (lazy, avec reconnexion automatique).
func NewClient(addr string) (*ValidatorClient, error) {
	conn, err := grpc.NewClient(addr,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		return nil, fmt.Errorf("new validator client: %w", err)
	}

	client := proto.NewValidatorClient(conn)
	return &ValidatorClient{conn: conn, client: client}, nil
}

// Close ferme la connexion gRPC.
func (c *ValidatorClient) Close() error {
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

// SignTicket envoie un payload au service Rust et retourne la signature HMAC.
func (c *ValidatorClient) SignTicket(ctx context.Context, payload *proto.TicketPayload) (string, error) {
	req := &proto.SignTicketRequest{Payload: payload}
	resp, err := c.client.SignTicket(ctx, req)
	if err != nil {
		return "", fmt.Errorf("sign ticket: %w", err)
	}
	if !resp.Success {
		return "", fmt.Errorf("validator: %s", resp.Error)
	}
	return resp.Signature, nil
}

// VerifyTicket vérifie une signature HMAC auprès du service Rust.
func (c *ValidatorClient) VerifyTicket(ctx context.Context, payload *proto.TicketPayload, signature string) (bool, error) {
	req := &proto.VerifyTicketRequest{Payload: payload, Signature: signature}
	resp, err := c.client.VerifyTicket(ctx, req)
	if err != nil {
		return false, fmt.Errorf("verify ticket: %w", err)
	}
	return resp.Valid, nil
}

// HealthCheck vérifie que le service Rust est disponible.
func (c *ValidatorClient) HealthCheck(ctx context.Context) (string, error) {
	resp, err := c.client.HealthCheck(ctx, &proto.HealthRequest{})
	if err != nil {
		return "", fmt.Errorf("health check: %w", err)
	}
	return resp.Status, nil
}
