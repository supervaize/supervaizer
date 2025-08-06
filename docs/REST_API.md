# REST API Documentation

SUPERVAIZER provides multiple ways to interact with and explore the API:

## Interactive REST API Documentation

### Swagger UI (`http://yourserver/docs`)

- **Interactive Testing**: Test API endpoints directly from the browser
- **Request Builder**: Build and execute API requests with real-time validation
- **Authentication**: Test authenticated endpoints using the API key
- **Schema Exploration**: Browse request/response schemas and data models
- **Try It Out**: Execute requests and see live responses

### ReDoc (`http://yourserver/redoc`)

- **Responsive Design**: Mobile-friendly documentation interface
- **Searchable**: Full-text search across all endpoints and schemas
- **Clean Layout**: Organized, easy-to-read API reference
- **Schema Examples**: Detailed examples for all request/response formats

### OpenAPI Schema (`http://yourserver/openapi.json`)

- **Machine Readable**: Complete OpenAPI 3.0 specification
- **Integration Ready**: Use with API clients and code generators
- **Schema Validation**: Validate requests against the specification

## Documentation URLs

When your server is running, you can access:

| Interface       | URL                                  | Description                 |
| --------------- | ------------------------------------ | --------------------------- |
| Swagger UI      | `http://localhost:8000/docs`         | Interactive API testing     |
| ReDoc           | `http://localhost:8000/redoc`        | API reference documentation |
| OpenAPI Schema  | `http://localhost:8000/openapi.json` | Machine-readable API spec   |
| Admin Dashboard | `http://localhost:8000/admin/`       | Web-based admin interface   |

## Authentication

Most endpoints support API key authentication:

- **Header**: `X-API-Key: your-api-key`
- **Auto-generated**: API key is automatically generated if not provided
- **Admin Interface**: Requires valid API key for access

## Example: Testing with Swagger UI

1. Start your SUPERVAIZER server
2. Navigate to `http://localhost:8000/docs`
3. Click "Authorize" and enter your API key
4. Browse available endpoints and test them directly
5. View request/response schemas and examples
