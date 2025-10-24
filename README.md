Aggregator berbasis Python (FastAPI) dengan idempotency, deduplication, dan persistence.

youtube: https://youtu.be/UCnV7B-b8dc
teori: https://docs.google.com/document/d/1Px_5KvLT47cLxEKdEYCHbQpv5q4sMYTi7Wsu3IzBSHg/edit?usp=sharing
pdf: https://drive.google.com/file/d/1Iq78pl4wD3wnonzzYfU7TGNUMyPXtAkQ/view?usp=sharing

---

### Build Image

```bash
docker build -t uts-aggregator .
```

### Run Container

```bash
docker run -p 8080:8080 uts-aggregator
```

### Atau dengan Docker Compose

```bash
docker-compose up --build
```

---

## Asumsi & Requirement

### Asumsi Implementasi

1. **Event Format**: Event JSON harus memiliki field: `topic`, `event_id`, `timestamp`, `source`, `payload`
2. **Deduplication Key**: Kombinasi `(topic, event_id)` digunakan sebagai unique identifier
3. **Persistence**: SQLite database disimpan di `/app/data/dedup.db` (untuk Docker)
4. **At-Least-Once Delivery**: Sistem dirancang untuk menangani event yang dikirim berulang kali
5. **Ordering**: Per-topic FIFO ordering, tidak ada global ordering antar topic berbeda
6. **Port**: Service berjalan di port 8080
7. **In-Memory Queue**: Event buffering menggunakan asyncio.Queue
8. **Local Only**: Tidak ada layanan eksternal (database, message broker, dll)

- **Python**: 3.11+
- **Framework**: FastAPI + Uvicorn
- **Database**: SQLite (persistent dedup store)
- **Async**: asyncio untuk concurrent processing
- **Validation**: Pydantic models

---

## API Endpoints

### 1. Health Check

```http
GET /
```

**Response:**

```json
{
  "service": "Event Aggregator",
  "status": "running",
  "version": "1.0.0"
}
```

---

### 2. Publish Event (Single)

```http
POST /publish
Content-Type: application/json
```

**Request Body:**

```json
{
  "topic": "order.created",
  "event_id": "evt-12345",
  "timestamp": "2025-10-24T10:30:00Z",
  "source": "order-service",
  "payload": {
    "order_id": "12345",
    "amount": 150000
  }
}
```

**Response (202 Accepted):**

```json
{
  "received": 1,
  "unique_processed": 1,
  "duplicate_dropped": 0,
  "message": "Received 1 event(s) for processing"
}
```

**cURL Example:**

```bash
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "order.created",
    "event_id": "evt-001",
    "timestamp": "2025-10-24T10:00:00Z",
    "source": "test",
    "payload": {"test": true}
  }'
```

---

### 3. Publish Event (Batch)

```http
POST /publish
Content-Type: application/json
```

**Request Body:**

```json
{
  "events": [
    {
      "topic": "user.registered",
      "event_id": "usr-001",
      "timestamp": "2025-10-24T11:00:00Z",
      "source": "auth-service",
      "payload": { "user_id": "123" }
    },
    {
      "topic": "payment.processed",
      "event_id": "pay-001",
      "timestamp": "2025-10-24T11:00:01Z",
      "source": "payment-service",
      "payload": { "amount": 50000 }
    }
  ]
}
```

**Response (202 Accepted):**

```json
{
  "received": 2,
  "unique_processed": 2,
  "duplicate_dropped": 0,
  "message": "Received 2 event(s) for processing"
}
```

---

### 4. Get Events

```http
GET /events
GET /events?topic=order.created
```

**Query Parameters:**

- `topic` (optional): Filter events by topic

**Response (200 OK):**

```json
{
  "topic": "order.created",
  "count": 2,
  "events": [
    {
      "topic": "order.created",
      "event_id": "evt-001",
      "timestamp": "2025-10-24T10:00:00Z",
      "source": "order-service",
      "payload": { "order_id": "12345" }
    },
    {
      "topic": "order.created",
      "event_id": "evt-002",
      "timestamp": "2025-10-24T10:05:00Z",
      "source": "order-service",
      "payload": { "order_id": "12346" }
    }
  ]
}
```

**cURL Example:**

```bash
# Get all events
curl http://localhost:8080/events

# Get events by topic
curl "http://localhost:8080/events?topic=order.created"
```

---

### 5. Get Statistics

```http
GET /stats
```

**Response (200 OK):**

```json
{
  "received": 5000,
  "unique_processed": 4000,
  "duplicate_dropped": 1000,
  "topics": ["order.created", "user.registered", "payment.processed"],
  "uptime_seconds": 123.45
}
```

**cURL Example:**

```bash
curl http://localhost:8080/stats
```

**Field Descriptions:**

- `received`: Total events diterima (termasuk duplikat)
- `unique_processed`: Event unik yang diproses
- `duplicate_dropped`: Event duplikat yang di-drop
- `topics`: List unique topics yang pernah diproses
- `uptime_seconds`: Waktu service berjalan (dalam detik)

---

## Testing

### Manual Testing

1. **Start service:**

```bash
docker run -p 8080:8080 uts-aggregator
```

2. **Send test event:**

```bash
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "test",
    "event_id": "test-001",
    "timestamp": "2025-10-24T10:00:00Z",
    "source": "manual",
    "payload": {}
  }'
```

3. **Send duplicate (should be dropped):**

```bash
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "test",
    "event_id": "test-001",
    "timestamp": "2025-10-24T10:00:01Z",
    "source": "manual",
    "payload": {}
  }'
```

4. **Check stats:**

```bash
curl http://localhost:8080/stats
# Should show: received=2, unique_processed=1, duplicate_dropped=1
```

### Automated Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest -v

# Run with coverage
pytest --cov=src --cov-report=html
```

### Load Testing

```bash
# Using publisher simulator
python publisher.py --events 5000 --duplicate-rate 0.2

# Expected: 4000 unique, 1000 duplicates
```

---

## Docker Details

### Image Structure

- **Base Image**: `python:3.11-slim`
- **User**: Non-root user (`appuser`)
- **Port**: 8080
- **Volume**: `/app/data` (untuk SQLite persistence)
- **Health Check**: HTTP GET ke `/`

### With Volume (Recommended)

```bash
# Create volume for persistence
docker volume create aggregator-data

# Run with volume
docker run -p 8080:8080 \
  -v aggregator-data:/app/data \
  uts-aggregator
```

### Check Logs

```bash
docker logs <container_id>
```

### Stop Container

```bash
docker stop <container_id>
```

---

## Docker Compose (Multi-Service)

File: `docker-compose.yml`

```bash
# Start aggregator + publisher
docker-compose up --build

# Run in background
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f aggregator
```

**Services:**

- `aggregator`: Event aggregator service (port 8080)
- `publisher`: Load testing simulator (auto sends 5000 events)

---

## Event Schema Validation

### Required Fields

- `topic` (string, min 1 char, tidak boleh whitespace)
- `event_id` (string, min 1 char, unique per topic)
- `timestamp` (ISO8601 datetime)
- `source` (string, min 1 char)
- `payload` (object/dict, arbitrary data)

### Validation Error Example

```bash
# Missing required field
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '{"topic": "test"}'

# Response: 422 Unprocessable Entity
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "event_id"],
      "msg": "Field required"
    },
    ...
  ]
}
```

---

## Deduplication & Idempotency

### How It Works

1. **Primary Key**: `(topic, event_id)` di SQLite
2. **Atomic Check**: INSERT dengan constraint violation = duplicate
3. **Persistence**: Database file di-mount sebagai volume
4. **Crash Resilient**: Dedup state survive restart

### Example

```bash
# First event - processed
POST /publish {"topic": "order", "event_id": "001", ...}
→ unique_processed += 1

# Duplicate event - dropped
POST /publish {"topic": "order", "event_id": "001", ...}
→ duplicate_dropped += 1

# Different topic, same ID - processed (different key)
POST /publish {"topic": "payment", "event_id": "001", ...}
→ unique_processed += 1
```

### Logging

```
INFO - Processed new event: topic=order, event_id=001
WARNING - Dropped duplicate event: topic=order, event_id=001
```

---

## Project Structure

```
uts/
├── src/
│   ├── main.py           # FastAPI app & endpoints
│   ├── models.py         # Pydantic models
│   ├── dedup_store.py    # SQLite dedup store
│   └── processor.py      # Event processor & queue
├── tests/
│   ├── test_*.py         # 34 unit tests
│   └── conftest.py       # Pytest fixtures
├── Dockerfile            # Aggregator image
├── Dockerfile.publisher  # Publisher image
├── docker-compose.yml    # Multi-service setup
├── requirements.txt      # Python dependencies
└── publisher.py          # Load simulator
```

---

## Configuration

### Environment Variables (Optional)

```bash
# For docker-compose
TOTAL_EVENTS=5000
DUPLICATE_RATE=0.2
BATCH_SIZE=50
```

### Database Location

- **Local**: `./data/dedup.db`
- **Docker**: `/app/data/dedup.db`

---

## Troubleshooting

### Port Already in Use

```bash
# Use different port
docker run -p 8081:8080 uts-aggregator
```

### Database Permission Error

```bash
# Ensure data directory exists and writable
mkdir -p data
chmod 755 data
```

### Container Exits Immediately

```bash
# Check logs
docker logs <container_id>

# Common: Port conflict or missing dependencies
```

### Reset Database

```bash
# Remove database file
rm -f data/dedup.db

# Or with Docker
docker-compose down -v
docker-compose up --build
```

---

## Performance

### Benchmarks

- **Throughput**: >1000 events/second
- **Test Load**: 5000 events (20% duplicates)
- **Processing**: ~4-5 seconds for 5000 events
- **Memory**: ~100MB runtime

### Scaling Limitations

- Single process (tidak distributed)
- SQLite write throughput (~1000 writes/s)
- In-memory event list (RAM bound)

**Note:** Untuk production scale, gunakan distributed message queue dan distributed cache.

---

## License

MIT License - Educational purposes

---

**Last Updated:** October 24, 2025
