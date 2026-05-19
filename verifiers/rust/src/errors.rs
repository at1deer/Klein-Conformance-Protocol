use thiserror::Error;

#[derive(Debug, Error)]
pub enum VerifyError {
    #[error("{0}")]
    Message(String),
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
    #[error(transparent)]
    Zip(#[from] zip::result::ZipError),
    #[error(transparent)]
    Base64(#[from] base64::DecodeError),
    #[error(transparent)]
    Ed25519(#[from] ed25519_dalek::SignatureError),
}

pub type Result<T> = std::result::Result<T, VerifyError>;

pub fn err(message: impl Into<String>) -> VerifyError {
    VerifyError::Message(message.into())
}
