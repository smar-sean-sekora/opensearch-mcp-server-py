# Add Docker and Docker Compose Support

**Priority**: Medium
**Estimated Time**: 1-2 hours
**Context**: Enable containerized deployment of the OpenSearch MCP Server with minimal Docker setup.

---

## Stage 1: Create Dockerfile
**Goal**: Build a containerized version of the MCP server

- [ ] Create `Dockerfile` in project root
- [ ] Use Python base image (python:3.11-slim)
- [ ] Install `uv` package manager
- [ ] Copy `pyproject.toml` and `uv.lock`
- [ ] Copy `src/` directory
- [ ] Set working directory to `/app/src`
- [ ] Set default command to run stdio server

**Notes**: Commands must run from `src/` directory. Support both stdio and streaming modes.

---

## Stage 2: Create Docker Compose and Environment Files
**Goal**: Provide docker-compose.yml and environment configuration

- [ ] Create `docker-compose.yml` in project root
- [ ] Define `mcp-server` service with build context
- [ ] Configure environment variables via `.env` file support
- [ ] Add volume mount for `config/` directory (multi-cluster mode)
- [ ] Create `.env.example` with all required variables:
  - OpenSearch connection (OPENSEARCH_URL, USERNAME, PASSWORD)
  - AWS credentials and region
  - IAM authentication settings
  - Index security patterns

**Notes**: Support both single and multi-cluster modes.

---

## Completion Checklist

- [ ] `Dockerfile` created
- [ ] `docker-compose.yml` created
- [ ] `.env.example` created
- [ ] Docker image builds successfully
