# Supervaizer Admin Interface

A lightweight web-based admin interface for managing WorkflowEntity objects (Jobs and Cases) using FastAPI, TinyDB, and HTMX.

## Features

### 🎯 **Core Functionality**

- **CRUD Operations**: Complete Create, Read, Update, Delete for Jobs and Cases
- **Real-time Updates**: HTMX-powered dynamic content loading without page refreshes
- **Responsive Design**: Modern UI built with Tailwind CSS
- **Advanced Filtering**: Filter by status, agent, job relations, search terms
- **Pagination**: Efficient handling of large datasets
- **Status Management**: Update entity statuses with proper lifecycle transitions

### 🔐 **Security**

- **API Key Authentication**: Secure access using X-API-Key header
- **Protected Endpoints**: All admin routes require valid API key
- **Session Management**: Proper authentication flow

### 📊 **Dashboard**

- **System Statistics**: Real-time counts of jobs and cases by status
- **Recent Activity**: Timeline of recent entity updates
- **System Status**: Database connection and health monitoring

## Installation & Setup

### 1. **Dependencies**

The admin interface requires the following dependencies (automatically installed):

```bash
uv add jinja2  # Template rendering
# TinyDB is already included in the base project
```

### 2. **Integration**

The admin interface is automatically integrated when creating a Server instance:

```python
from supervaizer.server import Server
from supervaizer.agent import Agent

# Create server with admin interface enabled
server = Server(
    agents=[your_agents],
    api_key="your-secure-api-key-here"  # Enables admin interface
)

# Admin routes are automatically mounted at /admin
server.launch()
```

### 3. **Access**

- **Base URL**: `http://localhost:8000/admin/`
- **Authentication**: Add header `X-API-Key: your-api-key`
- **Dashboard**: `http://localhost:8000/admin/`
- **Jobs Management**: `http://localhost:8000/admin/jobs`
- **Cases Management**: `http://localhost:8000/admin/cases`

## Architecture

### 📁 **File Structure**

```
src/supervaizer/admin/
├── routes.py              # FastAPI routes and API endpoints
└── templates/
    ├── base.html          # Base template with layout
    ├── dashboard.html     # Dashboard page
    ├── jobs_list.html     # Jobs management page
    ├── jobs_table.html    # Jobs table (HTMX partial)
    ├── cases_list.html    # Cases management page
    ├── cases_table.html   # Cases table (HTMX partial)
    ├── job_detail.html    # Job detail modal
    ├── case_detail.html   # Case detail modal
    └── recent_activity.html # Recent activity partial
```

### 🗄️ **Data Storage**

- **Backend**: TinyDB (JSON file-based database)
- **Storage Manager**: Uses existing `StorageManager` from `storage.py`
- **Collections**: Separate tables for "Job" and "Case" entities
- **Relationships**: Foreign key references (Job.case_ids, Case.job_id)

### 🔧 **Technical Stack**

- **Backend**: FastAPI with async/await support
- **Database**: TinyDB for lightweight persistence
- **Templates**: Jinja2 for server-side rendering
- **Frontend**: HTMX + Alpine.js + Tailwind CSS
- **Authentication**: API Key header-based

## API Endpoints

### 📱 **Page Routes**

- `GET /admin/` - Dashboard page
- `GET /admin/jobs` - Jobs management page
- `GET /admin/cases` - Cases management page

### 🔌 **API Routes**

- `GET /admin/api/stats` - System statistics
- `GET /admin/api/jobs` - Jobs list with filtering/pagination
- `GET /admin/api/jobs/{id}` - Job details
- `GET /admin/api/cases` - Cases list with filtering/pagination
- `GET /admin/api/cases/{id}` - Case details
- `POST /admin/api/jobs/{id}/status` - Update job status
- `POST /admin/api/cases/{id}/status` - Update case status
- `DELETE /admin/api/jobs/{id}` - Delete job (and related cases)
- `DELETE /admin/api/cases/{id}` - Delete case
- `GET /admin/api/recent-activity` - Recent activity feed

## Usage Examples

### 🚀 **Basic Setup**

```python
#!/usr/bin/env python3
from supervaizer.server import Server
from supervaizer.agent import Agent

# Create demo agent
demo_agent = Agent(
    name="demo_agent",
    description="Demo agent for testing"
)

# Create server with admin interface
server = Server(
    agents=[demo_agent],
    host="127.0.0.1",
    port=8000,
    api_key="my-secret-admin-key"
)

print("Admin interface: http://127.0.0.1:8000/admin/")
print("API Key: my-secret-admin-key")
server.launch()
```

### 🔍 **Filtering Examples**

```bash
# Filter jobs by status
GET /admin/api/jobs?status=completed

# Filter by agent name
GET /admin/api/jobs?agent_name=demo_agent

# Search jobs
GET /admin/api/jobs?search=important

# Combined filters with pagination
GET /admin/api/jobs?status=in_progress&agent_name=demo&limit=25&skip=0

# Filter cases by parent job
GET /admin/api/cases?job_id=12345

# Sort by creation date (descending)
GET /admin/api/cases?sort=-created_at
```

### 🔄 **Status Updates**

```bash
# Update job status
POST /admin/api/jobs/12345/status
Content-Type: application/json
X-API-Key: your-api-key

{"status": "completed"}

# Update case status
POST /admin/api/cases/67890/status
Content-Type: application/json
X-API-Key: your-api-key

{"status": "failed"}
```

## Features in Detail

### 📊 **Dashboard**

- **Job Statistics**: Total, running, completed, failed jobs
- **Case Statistics**: Total, running, completed, failed cases
- **System Info**: Database name, status, collection count
- **Recent Activity**: Last 10 entity updates with clickable details

### 👨‍💼 **Jobs Management**

- **List View**: Paginated table with job details
- **Filtering**: By status, agent name, search terms
- **Sorting**: By created date, name, status
- **Actions**: View details, update status, delete (with cascading case deletion)
- **Details Modal**: Complete job information including context and related cases

### 📁 **Cases Management**

- **List View**: Paginated table with case details
- **Filtering**: By status, parent job, search terms
- **Cost Tracking**: Display total cost per case
- **Parent Relations**: Direct links to parent jobs
- **Details Modal**: Complete case information including nodes, updates, and final delivery

### ⚡ **Real-time Features**

- **Auto-refresh**: Optional auto-refresh for live monitoring
- **Toast Notifications**: Success/error feedback for actions
- **Dynamic Loading**: HTMX partial updates without page reloads
- **Modal System**: Overlay details without navigation

## Security Considerations

### 🔐 **Authentication**

- **API Key Required**: All admin endpoints require valid API key
- **Environment Variables**: Use `SUPERVAIZER_API_KEY` environment variable
- **Auto-generation**: Falls back to auto-generated key with warning

### 🛡️ **Best Practices**

- **Strong API Keys**: Use long, random API keys in production
- **Environment Isolation**: Keep development and production keys separate
- **Access Logging**: All admin actions are logged
- **Input Validation**: All inputs are validated on server side

## Troubleshooting

### ❗ **Common Issues**

**Admin interface not accessible:**

- Ensure API key is set (`SUPERVAIZER_API_KEY` environment variable)
- Check X-API-Key header is included in requests
- Verify server is running with admin routes enabled

**Templates not loading:**

- Check template directory path in `routes.py`
- Ensure all template files exist in `src/supervaizer/admin/templates/`

**Database errors:**

- Verify TinyDB file permissions
- Check `DATA_STORAGE_PATH` environment variable
- Ensure storage directory exists and is writable

**HTMX not working:**

- Check browser console for JavaScript errors
- Verify HTMX script is loading from CDN
- Ensure proper HTMX attributes in templates

### 🔧 **Development Tips**

- Use `debug=True` for detailed error messages
- Check FastAPI auto-generated docs at `/docs`
- Monitor server logs for admin route registration
- Use browser dev tools to inspect HTMX requests

## Future Enhancements

### 🚀 **Planned Features**

- **Mission Management**: Add CRUD for Mission entities
- **Bulk Operations**: Multi-select actions for batch operations
- **Export/Import**: JSON/CSV export of entity data
- **Advanced Search**: Full-text search across all fields
- **Audit Trail**: Track all changes with timestamps and user info
- **Real-time WebSocket**: Live updates without polling
- **Role-based Access**: Different permission levels
- **Custom Dashboards**: Configurable widgets and metrics

### 🎨 **UI Improvements**

- **Dark Mode**: Toggle between light/dark themes
- **Mobile Optimization**: Better responsive design for mobile devices
- **Accessibility**: WCAG compliance improvements
- **Performance**: Virtual scrolling for large datasets

---

## Quick Test

Run the test script to verify everything works:

```bash
python test_admin.py
```

Then visit `http://127.0.0.1:8000/admin/` with API key `test-admin-key-123` in the `X-API-Key` header.

---

_For more information, see the main project documentation and API reference._
