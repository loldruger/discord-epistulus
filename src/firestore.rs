use std::sync::Arc;

use firestore::FirestoreDb;

pub enum FirestoreError {
    InvalidProjectId
}

pub async fn initialize_firestore() -> Result<Arc<FirestoreDb>, FirestoreError> {
    let project_id = std::env::var("FIRESTORE_PROJECT_ID")
        .map_err(|_| FirestoreError::InvalidProjectId)?;

    let db = FirestoreDb::new(project_id)
        .await
        .map_err(|_| FirestoreError::InvalidProjectId)?;

    Ok(Arc::new(db))
}

