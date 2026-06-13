use std::sync::Arc;
use tonic::{transport::Server, Request, Response, Status};
use tracing::{info, warn};

mod proto {
    tonic::include_proto!("validator");
}

use proto::{
    validator_server::{Validator, ValidatorServer},
    HealthRequest, HealthResponse,
    SignTicketRequest, SignTicketResponse,
    VerifyTicketRequest, VerifyTicketResponse,
};

use ring::hmac;
use serde_json;

/// Clé HMAC partagée (en production: injectée via env / vault)
const HMAC_SECRET: &[u8] = b"gaboom-validator-secret-key-2026";

#[derive(Debug, Default)]
pub struct TicketValidator;

impl TicketValidator {
    fn sign_payload(&self, payload: &proto::TicketPayload) -> Result<String, Status> {
        let json = serde_json::to_string(payload)
            .map_err(|e| Status::internal(format!("serialization error: {}", e)))?;

        let key = hmac::Key::new(hmac::HMAC_SHA256, HMAC_SECRET);
        let signature = hmac::sign(&key, json.as_bytes());

        Ok(hex::encode(signature.as_ref()))
    }

    fn verify_payload(&self, payload: &proto::TicketPayload, signature_hex: &str) -> Result<bool, Status> {
        let json = serde_json::to_string(payload)
            .map_err(|e| Status::internal(format!("serialization error: {}", e)))?;

        let key = hmac::Key::new(hmac::HMAC_SHA256, HMAC_SECRET);
        let signature_bytes = hex::decode(signature_hex)
            .map_err(|e| Status::invalid_argument(format!("invalid hex: {}", e)))?;

        match hmac::verify(&key, json.as_bytes(), &signature_bytes) {
            Ok(_) => Ok(true),
            Err(_) => Ok(false),
        }
    }
}

#[tonic::async_trait]
impl Validator for TicketValidator {
    async fn sign_ticket(
        &self,
        request: Request<SignTicketRequest>,
    ) -> Result<Response<SignTicketResponse>, Status> {
        let req = request.into_inner();
        let payload = req.payload.ok_or_else(|| Status::invalid_argument("payload required"))?;

        info!("Signing ticket {}", payload.ticket_uuid);

        match self.sign_payload(&payload) {
            Ok(signature) => Ok(Response::new(SignTicketResponse {
                signature,
                ticket_uuid: payload.ticket_uuid.clone(),
                success: true,
                error: "".into(),
            })),
            Err(e) => {
                warn!("Sign error: {}", e);
                Ok(Response::new(SignTicketResponse {
                    signature: "".into(),
                    ticket_uuid: payload.ticket_uuid.clone(),
                    success: false,
                    error: e.to_string(),
                }))
            }
        }
    }

    async fn verify_ticket(
        &self,
        request: Request<VerifyTicketRequest>,
    ) -> Result<Response<VerifyTicketResponse>, Status> {
        let req = request.into_inner();
        let payload = req.payload.ok_or_else(|| Status::invalid_argument("payload required"))?;

        info!("Verifying ticket {}", payload.ticket_uuid);

        match self.verify_payload(&payload, &req.signature) {
            Ok(valid) => Ok(Response::new(VerifyTicketResponse {
                valid,
                ticket_uuid: payload.ticket_uuid.clone(),
                error: "".into(),
            })),
            Err(e) => {
                warn!("Verify error: {}", e);
                Ok(Response::new(VerifyTicketResponse {
                    valid: false,
                    ticket_uuid: payload.ticket_uuid.clone(),
                    error: e.to_string(),
                }))
            }
        }
    }

    async fn health_check(
        &self,
        _request: Request<HealthRequest>,
    ) -> Result<Response<HealthResponse>, Status> {
        Ok(Response::new(HealthResponse {
            status: "ok".into(),
        }))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt::init();

    let addr = "0.0.0.0:50051".parse()?;
    let validator = TicketValidator::default();

    info!("Validator gRPC server listening on {}", addr);

    Server::builder()
        .add_service(ValidatorServer::new(validator))
        .serve(addr)
        .await?;

    Ok(())
}
