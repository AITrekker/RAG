# HR RAG Pipeline: Intelligent HR Document Assistant

## 1. Overview

This project is a sophisticated, multi-tenant Retrieval-Augmented Generation (RAG) system designed to power an intelligent HR support application. It allows HR staff to ask natural language questions and receive accurate, context-aware answers based on a private, internal corpus of HR documents (e.g., policies, employee handbooks, legal documents).

The system is built with a local-first, self-hosted architecture for maximum data privacy and control, with a clear and easy path to cloud deployment. It ingests documents from specified local folders, processes them into a searchable vector database, and uses a generative LLM to provide answers, all while ensuring strict data isolation between tenants.

## 2. Core Features (MVP)

- **Multi-Tenant Architecture:** Securely supports multiple tenants with complete data isolation at the database, file system, and processing levels.
- **Automated Document Ingestion:** Monitors tenant-specific folders for new, modified, or deleted documents and automatically syncs them.
- **Delta Synchronization:** Efficiently processes only the changes in documents rather than re-processing entire files, saving time and computational resources.
- **Advanced RAG Pipeline:**
  - Utilizes state-of-the-art embedding models for high-quality semantic search.
  - Employs a sophisticated reranking step to improve the relevance of retrieved documents.
  - Generates responses using a locally-hosted Large Language Model (LLM) for privacy.
- **File Versioning:** Tracks changes to documents and embeddings, allowing for consistency and auditability.
- **Sync Reporting:** Provides a reporting interface with an interactive calendar to view the status and history of synchronization tasks.
- **Dockerized Environment:** Fully containerized with Docker for consistent development, testing, and deployment.

## 3. Architecture Overview

The system follows a modular RAG architecture:

1.  **File Ingestion & Sync:** A file system watcher monitors designated folders for each tenant. A sync process detects new, updated, and deleted files.
2.  **Document Processing Pipeline:** LlamaIndex orchestrates the processing of documents. It loads content, splits it into chunks, and generates vector embeddings using a Hugging Face `transformers` model running on a local GPU.
3.  **Metadata & Vector Storage:** A PostgreSQL/SQLite database stores file metadata, versions, and sync status. A vector store (e.g., FAISS, Chroma) stores the embeddings for efficient similarity search. All data is isolated by a `tenant_id`.
4.  **RAG Query Pipeline:**
    - An incoming query is processed.
    - A hybrid search retrieves relevant document chunks by filtering on metadata and performing a vector search.
    - A reranking model refines the search results for maximum relevance.
    - The final context is passed to a local generative LLM (via `transformers`) to synthesize an answer.
5.  **API & UI:** A FastAPI backend exposes the RAG functionality. A simple UI provides a query interface and a reporting dashboard.

## 4. Technology Stack

- **Backend:** Python, FastAPI
- **RAG & ML:** LlamaIndex, Hugging Face `transformers`, PyTorch
- **Database:** SQLAlchemy, Alembic (for migrations), SQLite (for local dev), PostgreSQL (for prod)
- **Vector Store:** Chroma / FAISS (to be decided)
- **Deployment:** Docker, Docker Compose
- **Frontend:** React, TypeScript (as per plan)

## 5. Getting Started (Local Development)

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd hr-rag-pipeline
    ```

2.  **Configure Environment:**
    - Copy the `.env.example` file to `.env`.
    - Populate the `.env` file with your local configuration details (database paths, folder paths, etc.).

3.  **Build and Run with Docker:**
    - Ensure you have Docker and Docker Compose installed, along with the NVIDIA Container Toolkit for GPU support.
    - Run the following command:
    ```bash
    docker-compose up --build
    ```

4.  **Access the Application:**
    - The API will be available at `http://localhost:8000`.
    - The UI will be available at `http://localhost:3000`.

## 6. Project Roadmap

This `README` outlines the plan for the initial MVP. We have a comprehensive roadmap for future development, including:

- **Phase 2:** Enhanced Security and Access Control
- **Phase 3:** MVP+ Core Feature Enhancements
- **Phase 4:** Advanced Application Features
- **Phase 5:** Conversation and Feedback
- **Phase 6:** Enhanced UI/UX
- **Phase 7:** Integration and Scaling

For a detailed breakdown of all current and future tasks, please see the `tasks/tasks-prd-hr-rag-pipeline.md` file.
