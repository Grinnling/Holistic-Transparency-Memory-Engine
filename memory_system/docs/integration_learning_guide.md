# React Frontend Integration Guide
## Learning What's Important + Building What's Missing

---

## 🎯 **Core Concepts You Need to Understand**

### **1. The Component Hierarchy**
```
App.tsx (Main orchestrator)
├── ErrorPanel.tsx (Error intelligence - what Claude needs!)
├── ServiceStatusPanel.tsx (Service health monitoring) ⚠️ MISSING
├── FileUploadPanel.tsx (File handling) ⚠️ MISSING
└── ConversationList.tsx (Chat switching) ⚠️ NOT USED YET
```

**Why this matters:**
- **App.tsx** = Brain (manages state, WebSocket, API calls)
- **Panels** = Organs (each has one job, reports to brain)
- **Shadcn/UI** = Skin (makes it look good, handles interactions)

### **2. State Management Flow**
```
User types message
    ↓
App.tsx captures input
    ↓
Sends to backend via fetch(/chat)
    ↓
Backend processes (your rich_chat.py)
    ↓
Backend sends via WebSocket
    ↓
App.tsx receives, updates state
    ↓
React re-renders with new message
```

**Why this matters:**
- React is **declarative**: "Show this data" not "Change this DOM element"
- State changes trigger re-renders automatically
- WebSocket keeps UI in sync with terminal backend

### **3. The Data Flow Triangle**
```
        Backend (Python)
        api_server.py
       /              \
      /                \
WebSocket            REST API
(real-time)       (on-demand)
     |                  |
     |                  |
     \                 /
      \               /
       \             /
        React Frontend
          App.tsx
```

**Why this matters:**
- **REST** for actions (send message, upload file)
- **WebSocket** for updates (new message, error occurred)
- **Both** needed for responsive UI

---

## 📦 **Step 1: Project Setup**

### **1.1 Create Next.js Project**
```bash
# Create project (if not already done)
npx create-next-app@latest memory-chat-ui
# Choose these options:
# ✓ TypeScript: Yes
# ✓ ESLint: Yes
# ✓ Tailwind CSS: Yes
# ✓ src/ directory: No
# ✓ App Router: Yes
# ✓ Import alias: No

cd memory-chat-ui
```

**What this does:**
- Creates React project with TypeScript (catches errors)
- Sets up Tailwind (styling without CSS files)
- Configures build system (Next.js handles bundling)

### **1.2 Install Shadcn/UI**
```bash
# Initialize shadcn
npx shadcn-ui@latest init

# Choose these options:
# Style: Default
# Base color: Slate
# CSS variables: Yes

# Install components we need
npx shadcn-ui@latest add card
npx shadcn-ui@latest add button
npx shadcn-ui@latest add input
npx shadcn-ui@latest add badge
npx shadcn-ui@latest add tabs
npx shadcn-ui@latest add scroll-area
npx shadcn-ui@latest add separator
npx shadcn-ui@latest add collapsible
npx shadcn-ui@latest add textarea
```

**What this does:**
- Creates `components/ui/` folder with pre-built components
- Each component is fully customizable (you own the code)
- No external dependencies needed after install

### **1.3 Project Structure**
```
memory-chat-ui/
├── app/
│   ├── page.tsx          # Main entry (replace with our App.tsx)
│   ├── layout.tsx        # Root layout (keep default)
│   └── globals.css       # Global styles (keep default)
├── components/
│   ├── ui/               # Shadcn components (auto-generated)
│   ├── ErrorPanel.tsx    # ✅ We have this
│   ├── ServiceStatusPanel.tsx  # ⚠️ We'll build this
│   └── FileUploadPanel.tsx     # ⚠️ We'll build this
└── lib/
    └── utils.ts          # Helper functions (auto-generated)
```

---

## 🔧 **Step 2: Build Missing Components**

### **2.1 ServiceStatusPanel.tsx**

**What it does:**
- Shows health of 4 services (working_memory, curator, mcp_logger, episodic_memory)
- Displays latency, error counts
- Provides toggle buttons for testing
- Shows conversation metadata

**Key concepts:**
```typescript
// Props = Data passed from parent (App.tsx)
interface ServiceStatusPanelProps {
  services: ServiceStatus;        // Current service health
  conversationId: string;         // Active conversation
}

// Component = Function that returns JSX
const ServiceStatusPanel = ({ services, conversationId }: ServiceStatusPanelProps) => {
  // Return JSX (HTML-like syntax)
  return <div>...</div>;
};
```

**Create file:** `components/ServiceStatusPanel.tsx`

```typescript
// components/ServiceStatusPanel.tsx
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Separator } from './ui/separator';
import { 
  CheckCircle, 
  XCircle, 
  AlertCircle, 
  Power,
  RefreshCw,
  Activity,
  Clock,
  AlertTriangle
} from 'lucide-react';

interface ServiceStatus {
  [serviceName: string]: {
    status: 'healthy' | 'unhealthy' | 'degraded' | 'starting' | 'stopped';
    latency?: number;
    last_check: string;
    error_count?: number;
  };
}

interface ServiceStatusPanelProps {
  services: ServiceStatus;
  conversationId: string;
  onToggleService?: (service: string, action: 'start' | 'stop' | 'restart') => void;
}

const ServiceStatusPanel: React.FC<ServiceStatusPanelProps> = ({ 
  services, 
  conversationId,
  onToggleService 
}) => {
  
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'unhealthy':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'degraded':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case 'starting':
        return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'bg-green-100 text-green-800 border-green-200';
      case 'unhealthy': return 'bg-red-100 text-red-800 border-red-200';
      case 'degraded': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'starting': return 'bg-blue-100 text-blue-800 border-blue-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const handleServiceToggle = (service: string, action: 'start' | 'stop' | 'restart') => {
    if (onToggleService) {
      onToggleService(service, action);
    }
  };

  const serviceList = Object.entries(services);
  const healthyCount = serviceList.filter(([_, s]) => s.status === 'healthy').length;
  const totalServices = serviceList.length;

  return (
    <div className="space-y-4">
      {/* Overall Health Summary */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Activity className="h-4 w-4" />
              System Health
            </span>
            <Badge variant={healthyCount === totalServices ? "default" : "destructive"}>
              {healthyCount}/{totalServices} Healthy
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Conversation ID:</span>
              <span className="font-mono text-xs">{conversationId.substring(0, 8)}...</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Individual Services */}
      {serviceList.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            No services detected. Start the backend services.
          </CardContent>
        </Card>
      ) : (
        serviceList.map(([serviceName, serviceData]) => (
          <Card key={serviceName}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {getStatusIcon(serviceData.status)}
                  <span className="font-medium text-sm capitalize">
                    {serviceName.replace(/_/g, ' ')}
                  </span>
                </div>
                <Badge 
                  variant="outline" 
                  className={getStatusColor(serviceData.status)}
                >
                  {serviceData.status}
                </Badge>
              </div>
            </CardHeader>
            
            <CardContent className="space-y-3">
              {/* Service Metrics */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                {serviceData.latency !== undefined && (
                  <div className="flex items-center gap-1">
                    <Clock className="h-3 w-3 text-gray-400" />
                    <span className="text-gray-600">Latency:</span>
                    <span className="font-medium">{serviceData.latency}ms</span>
                  </div>
                )}
                
                {serviceData.error_count !== undefined && (
                  <div className="flex items-center gap-1">
                    <AlertCircle className="h-3 w-3 text-gray-400" />
                    <span className="text-gray-600">Errors:</span>
                    <span className="font-medium">{serviceData.error_count}</span>
                  </div>
                )}
              </div>

              <div className="text-xs text-gray-500">
                Last check: {new Date(serviceData.last_check).toLocaleTimeString()}
              </div>

              <Separator />

              {/* Service Controls */}
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="flex-1"
                  onClick={() => handleServiceToggle(serviceName, 'restart')}
                >
                  <RefreshCw className="h-3 w-3 mr-1" />
                  Restart
                </Button>
                
                <Button
                  size="sm"
                  variant={serviceData.status === 'stopped' ? 'default' : 'outline'}
                  className="flex-1"
                  onClick={() => handleServiceToggle(
                    serviceName, 
                    serviceData.status === 'stopped' ? 'start' : 'stop'
                  )}
                >
                  <Power className="h-3 w-3 mr-1" />
                  {serviceData.status === 'stopped' ? 'Start' : 'Stop'}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
};

export default ServiceStatusPanel;
```

**What's important here:**
- **Props typing** - TypeScript ensures correct data passed
- **Conditional rendering** - Shows different UI based on data
- **Event handlers** - onClick callbacks to parent component
- **Icon usage** - Lucide icons for visual clarity
- **Responsive layout** - Grid system for metrics

---

### **2.2 FileUploadPanel.tsx**

**What it does:**
- Drag & drop file upload
- Preview uploaded files
- Show file metadata (type, size)
- Organize by conversation

**Key concepts:**
```typescript
// File handling in React
const handleDrop = (e: React.DragEvent) => {
  e.preventDefault();
  const files = e.dataTransfer.files;
  // Process files...
};

// State for file list
const [uploadedFiles, setUploadedFiles] = useState([]);
```

**Create file:** `components/FileUploadPanel.tsx`

```typescript
// components/FileUploadPanel.tsx
import React, { useState, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { 
  Upload, 
  File, 
  FileText, 
  Image, 
  Video, 
  Music,
  Code,
  Archive,
  X,
  Download
} from 'lucide-react';

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  uploadedAt: string;
  preview?: string;
}

interface FileUploadPanelProps {
  onFileUpload?: (files: File[]) => void;
}

const FileUploadPanel: React.FC<FileUploadPanelProps> = ({ onFileUpload }) => {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const getFileIcon = (fileType: string) => {
    if (fileType.startsWith('image/')) return <Image className="h-5 w-5" />;
    if (fileType.startsWith('video/')) return <Video className="h-5 w-5" />;
    if (fileType.startsWith('audio/')) return <Music className="h-5 w-5" />;
    if (fileType.includes('pdf') || fileType.includes('document')) 
      return <FileText className="h-5 w-5" />;
    if (fileType.includes('zip') || fileType.includes('tar')) 
      return <Archive className="h-5 w-5" />;
    if (fileType.includes('javascript') || fileType.includes('python'))
      return <Code className="h-5 w-5" />;
    return <File className="h-5 w-5" />;
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    await processFiles(files);
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      await processFiles(files);
    }
  };

  const processFiles = async (files: File[]) => {
    // Convert File objects to UploadedFile format
    const newFiles: UploadedFile[] = files.map(file => ({
      id: `${Date.now()}-${file.name}`,
      name: file.name,
      size: file.size,
      type: file.type,
      uploadedAt: new Date().toISOString(),
      preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined
    }));

    setUploadedFiles(prev => [...prev, ...newFiles]);

    // Notify parent component
    if (onFileUpload) {
      onFileUpload(files);
    }

    // TODO: Actually upload to backend
    console.log('Files to upload:', files);
  };

  const removeFile = (fileId: string) => {
    setUploadedFiles(prev => prev.filter(f => f.id !== fileId));
  };

  return (
    <Card className="h-full flex flex-col">
      <CardHeader>
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Upload className="h-4 w-4" />
          File Management
        </CardTitle>
      </CardHeader>

      <CardContent className="flex-1 flex flex-col space-y-4">
        {/* Drop Zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`
            border-2 border-dashed rounded-lg p-8 text-center
            transition-colors cursor-pointer
            ${isDragging 
              ? 'border-blue-500 bg-blue-50' 
              : 'border-gray-300 hover:border-gray-400'
            }
          `}
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload className={`h-12 w-12 mx-auto mb-4 ${isDragging ? 'text-blue-500' : 'text-gray-400'}`} />
          <p className="text-sm font-medium mb-2">
            {isDragging ? 'Drop files here' : 'Drag & drop files here'}
          </p>
          <p className="text-xs text-gray-500 mb-4">
            or click to browse
          </p>
          <Button variant="outline" size="sm">
            Select Files
          </Button>
          
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            className="hidden"
          />
        </div>

        {/* Uploaded Files List */}
        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium">
              Uploaded Files ({uploadedFiles.length})
            </h3>
          </div>

          <ScrollArea className="h-[400px]">
            {uploadedFiles.length === 0 ? (
              <div className="text-center py-8 text-gray-500 text-sm">
                No files uploaded yet
              </div>
            ) : (
              <div className="space-y-2">
                {uploadedFiles.map(file => (
                  <Card key={file.id} className="p-3">
                    <div className="flex items-start gap-3">
                      {/* File Preview/Icon */}
                      <div className="flex-shrink-0">
                        {file.preview ? (
                          <img 
                            src={file.preview} 
                            alt={file.name}
                            className="h-12 w-12 object-cover rounded"
                          />
                        ) : (
                          <div className="h-12 w-12 bg-gray-100 rounded flex items-center justify-center text-gray-600">
                            {getFileIcon(file.type)}
                          </div>
                        )}
                      </div>

                      {/* File Info */}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">
                          {file.name}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant="outline" className="text-xs">
                            {formatFileSize(file.size)}
                          </Badge>
                          <span className="text-xs text-gray-500">
                            {new Date(file.uploadedAt).toLocaleTimeString()}
                          </span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0"
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0"
                          onClick={() => removeFile(file.id)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </ScrollArea>
        </div>
      </CardContent>
    </Card>
  );
};

export default FileUploadPanel;
```

**What's important here:**
- **Drag & drop events** - onDragOver, onDrop handlers
- **File handling** - FileReader API for previews
- **Ref usage** - fileInputRef to trigger hidden input
- **State management** - Track uploaded files
- **Visual feedback** - isDragging state for UI changes

---

## 🔌 **Step 3: Wire Everything Together**

### **3.1 Update App.tsx**

Replace `app/page.tsx` with the App.tsx from the artifact, making sure imports match your file structure:

```typescript
// At top of app/page.tsx
import ErrorPanel from '../components/ErrorPanel';
import ServiceStatusPanel from '../components/ServiceStatusPanel';
import FileUploadPanel from '../components/FileUploadPanel';
```

### **3.2 Add Service Toggle Handler**

In App.tsx, add this function:

```typescript
const handleServiceToggle = async (service: string, action: 'start' | 'stop' | 'restart') => {
  try {
    // TODO: Implement service control endpoint in backend
    console.log(`${action} service: ${service}`);
    
    // Optimistic UI update
    setServiceStatus(prev => ({
      ...prev,
      [service]: {
        ...prev[service],
        status: action === 'stop' ? 'stopped' : 'starting'
      }
    }));
    
    // Call backend when endpoint exists
    // await fetch(`${API_BASE}/services/${service}/${action}`, { method: 'POST' });
    
  } catch (error) {
    console.error(`Failed to ${action} service:`, error);
  }
};
```

Then pass it to ServiceStatusPanel:

```typescript
<ServiceStatusPanel 
  services={serviceStatus}
  conversationId={conversationId}
  onToggleService={handleServiceToggle}  // Add this
/>
```

### **3.3 Add File Upload Handler**

```typescript
const handleFileUpload = async (files: File[]) => {
  try {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    
    // TODO: Implement file upload endpoint in backend
    console.log('Uploading files:', files);
    
    // await fetch(`${API_BASE}/files/upload`, {
    //   method: 'POST',
    //   body: formData
    // });
    
  } catch (error) {
    console.error('Failed to upload files:', error);
  }
};
```

Then pass it to FileUploadPanel:

```typescript
<FileUploadPanel onFileUpload={handleFileUpload} />
```

---

## ✅ **Step 4: Test the Frontend**

### **4.1 Start Development Server**

```bash
npm run dev
```

Visit: http://localhost:3000

### **4.2 What Should Work**

**✅ Without Backend:**
- UI renders
- Components display
- Drag & drop files (stored in memory)
- Service status shows "no services"
- Error panel empty

**✅ With Backend (when you start api_server.py):**
- WebSocket connects
- Messages send/receive
- Errors populate panel
- Service status updates
- Real-time sync

### **4.3 Expected Errors (Normal)**

```
Failed to fetch http://localhost:8000/health
WebSocket connection failed
```

**This is NORMAL** until you start the backend!

---

## 🎓 **Key Takeaways for Learning**

### **1. Component Communication**
```
Parent (App.tsx)
  ├─ Manages state (messages, errors, services)
  ├─ Passes data down as props
  └─ Receives events up via callbacks

Child (ErrorPanel)
  ├─ Receives data via props
  ├─ Displays data
  └─ Calls parent callbacks on user actions
```

### **2. State Updates**
```typescript
// ❌ DON'T mutate state directly
errors.push(newError);

// ✅ DO create new state
setErrors(prev => [...prev, newError]);
```

### **3. TypeScript Benefits**
```typescript
// TypeScript catches this error at compile time:
<ErrorPanel errors="wrong type" />  // Error!

// Must be:
<ErrorPanel errors={[]} />  // Correct!
```

### **4. React Hooks Pattern**
```typescript
// State: Data that changes
const [count, setCount] = useState(0);

// Effect: Side effects (API calls, subscriptions)
useEffect(() => {
  // Runs on mount and when dependencies change
  fetchData();
}, [dependencies]);

// Ref: Direct DOM access (not reactive)
const inputRef = useRef<HTMLInputElement>(null);
```

---

## 📋 **Next Steps Checklist**

### **Phase 1: Core Functionality (Do First)**
- [ ] Create Next.js project
- [ ] Install Shadcn/UI components
- [ ] Create ServiceStatusPanel.tsx
- [ ] Create FileUploadPanel.tsx
- [ ] Update App.tsx imports
- [ ] Add service toggle handler
- [ ] Add file upload handler
- [ ] Test frontend (npm run dev)
- [ ] Start backend (python api_server.py)
- [ ] Test full integration

### **Phase 2: Enhanced Intelligence (After Backend Works)**

**2.1 Message ↔ Error Linking** (~30 minutes)
*Helps Claude understand what caused each error*

**Backend Changes:**
```python
# In api_server.py - track_error function
def track_error(error: str, operation_context: str = None, 
                service: str = None, severity: str = "normal",
                triggering_message_id: str = None,
                conversation_state: dict = None):
    """Enhanced error tracking with message context"""
    error_event = ErrorEvent(
        id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        error=error,
        operation_context=operation_context,
        service=service,
        severity=severity,
        triggering_message_id=triggering_message_id,  # NEW
        related_messages=get_last_n_messages(3),      # NEW: Last 3 messages
        conversation_state=conversation_state          # NEW: System state
    )
```

**Frontend Changes:**
```typescript
// In ErrorPanel.tsx - show message context
{error.triggering_message_id && (
  <div className="text-xs bg-gray-50 p-2 rounded mt-2">
    <div className="font-medium text-gray-700">Triggered by:</div>
    <div className="text-gray-600 font-mono">
      {getMessageById(error.triggering_message_id)?.content.substring(0, 100)}...
    </div>
  </div>
)}

{error.related_messages && error.related_messages.length > 0 && (
  <details className="text-xs mt-2">
    <summary className="cursor-pointer text-gray-600">
      View conversation context ({error.related_messages.length} messages)
    </summary>
    <div className="mt-1 space-y-1 ml-2">
      {error.related_messages.map((msgId, i) => (
        <div key={i} className="text-gray-500 font-mono">
          → {getMessageById(msgId)?.content.substring(0, 80)}...
        </div>
      ))}
    </div>
  </details>
)}
```

**Testing:**
- [ ] Error shows which message triggered it
- [ ] Can see last 3 messages in error context
- [ ] Conversation state captured (message count, confidence)

---

**2.2 Memory Query Visibility** (~1 hour)
*Helps Claude see what memory searches are happening*

**Backend Changes:**
```python
# In api_server.py - add memory query broadcasting
@app.post("/chat")
async def chat_endpoint(message: ChatMessage):
    # ... existing code ...
    
    # NEW: Broadcast memory queries as they happen
    async def broadcast_memory_query(query: str, results: list, 
                                    message_id: str, query_type: str):
        await broadcast_to_react({
            "type": "memory_query",
            "query": query,
            "results_found": len(results),
            "relevance_scores": [r.score for r in results[:5]],
            "search_time_ms": search_duration,
            "message_id": message_id,
            "query_type": query_type
        })
```

**Frontend Changes - New Component:**
```typescript
// components/MemoryActivityPanel.tsx
const MemoryActivityPanel = ({ queries }) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Memory Activity</CardTitle>
      </CardHeader>
      <CardContent>
        {queries.map(query => (
          <div key={query.id} className="border-l-2 border-blue-500 pl-3 mb-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{query.query}</span>
              <Badge>{query.results_found} results</Badge>
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {query.search_time_ms}ms · {query.query_type}
            </div>
            {query.relevance_scores.length > 0 && (
              <div className="flex gap-1 mt-2">
                {query.relevance_scores.map((score, i) => (
                  <div 
                    key={i}
                    className="h-2 w-8 bg-blue-200 rounded"
                    style={{ opacity: score }}
                  />
                ))}
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
};
```

**Add to App.tsx:**
```typescript
// Add new state
const [memoryQueries, setMemoryQueries] = useState([]);

// In handleWebSocketMessage:
case 'memory_query':
  setMemoryQueries(prev => [...prev, data].slice(-20)); // Keep last 20
  break;

// Add new tab in sidebar
<TabsTrigger value="memory">Memory Activity</TabsTrigger>
<TabsContent value="memory">
  <MemoryActivityPanel queries={memoryQueries} />
</TabsContent>
```

**Testing:**
- [ ] Memory queries appear in real-time
- [ ] Shows relevance scores visually
- [ ] Links to messages that triggered queries
- [ ] Search times tracked

---

### **Phase 3: Advanced Analytics (Polish Phase)**

**3.1 Confidence Trends** (~1 hour)
*Helps Claude spot degradation patterns*

**Backend Changes:**
```python
# In api_server.py - track confidence trends
class ConfidenceTracker:
    def __init__(self):
        self.history = []
    
    def add_response(self, confidence: float, topic: str = None):
        self.history.append({
            'confidence': confidence,
            'topic': topic,
            'timestamp': datetime.now()
        })
        
        # Broadcast trend updates
        if len(self.history) >= 10:
            await self.broadcast_trend_update()
    
    async def broadcast_trend_update(self):
        last_10 = self.history[-10:]
        current_avg = sum(h['confidence'] for h in last_10) / 10
        
        # Detect trend
        first_5 = sum(h['confidence'] for h in last_10[:5]) / 5
        last_5 = sum(h['confidence'] for h in last_10[5:]) / 5
        
        trend = 'stable'
        if last_5 > first_5 + 0.1:
            trend = 'improving'
        elif last_5 < first_5 - 0.1:
            trend = 'degrading'
        
        await broadcast_to_react({
            "type": "confidence_trend",
            "current_average": current_avg,
            "last_10_average": current_avg,
            "trend": trend,
            "low_confidence_topics": self.get_low_confidence_topics()
        })
```

**Frontend Changes:**
```typescript
// In ServiceStatusPanel.tsx - add confidence trend display
<Card>
  <CardHeader>
    <CardTitle className="flex items-center gap-2">
      Confidence Trend
      {trend === 'degrading' && (
        <Badge variant="destructive">Degrading</Badge>
      )}
    </CardTitle>
  </CardHeader>
  <CardContent>
    <div className="text-2xl font-bold">
      {Math.round(currentAverage * 100)}%
    </div>
    <div className="text-xs text-gray-500">
      Average over last 10 responses
    </div>
    
    {/* Simple sparkline */}
    <div className="flex items-end gap-1 h-8 mt-2">
      {confidenceHistory.map((score, i) => (
        <div
          key={i}
          className="flex-1 bg-blue-500 rounded-t"
          style={{ height: `${score * 100}%` }}
        />
      ))}
    </div>
  </CardContent>
</Card>
```

**Testing:**
- [ ] Confidence trend updates after 10 messages
- [ ] Visual sparkline shows trend
- [ ] Alerts when degrading
- [ ] Identifies low-confidence topics

---

**3.2 Service Health History** (~1 hour)
*Helps Claude identify chronic service issues*

**Backend Changes:**
```python
# In api_server.py - track service health over time
class ServiceHealthTracker:
    def __init__(self):
        self.history = defaultdict(lambda: {
            'health_scores': [],
            'latencies': [],
            'status_changes': []
        })
    
    async def record_health_check(self, service: str, is_healthy: bool, 
                                  latency: float):
        history = self.history[service]
        
        # Add health score (100 = healthy, 0 = unhealthy)
        history['health_scores'].append(100 if is_healthy else 0)
        history['latencies'].append(latency)
        
        # Keep last 20 only
        history['health_scores'] = history['health_scores'][-20:]
        history['latencies'] = history['latencies'][-20:]
        
        # Broadcast if patterns detected
        if self.detect_chronic_issue(service):
            await self.broadcast_health_warning(service)
    
    def detect_chronic_issue(self, service: str) -> bool:
        scores = self.history[service]['health_scores']
        if len(scores) < 10:
            return False
        
        # More than 50% failures in last 10 checks
        recent_failures = sum(1 for s in scores[-10:] if s < 50)
        return recent_failures > 5
```

**Frontend Changes:**
```typescript
// In ServiceStatusPanel.tsx - add health history sparkline
<div className="mt-2">
  <div className="text-xs text-gray-600 mb-1">Health History</div>
  <div className="flex items-end gap-0.5 h-6">
    {healthHistory.map((score, i) => (
      <div
        key={i}
        className={`flex-1 rounded-t ${
          score > 80 ? 'bg-green-500' :
          score > 50 ? 'bg-yellow-500' :
          'bg-red-500'
        }`}
        style={{ height: `${score}%` }}
      />
    ))}
  </div>
  
  {chronicIssues && chronicIssues.length > 0 && (
    <div className="mt-2 text-xs text-red-600">
      ⚠️ Chronic issues detected:
      {chronicIssues.map(issue => (
        <div key={issue} className="ml-2">• {issue}</div>
      ))}
    </div>
  )}
</div>
```

**Testing:**
- [ ] Health sparkline shows last 20 checks
- [ ] Colors indicate health (green/yellow/red)
- [ ] Chronic issues flagged
- [ ] Status change history tracked

---



## 🤔 **Common Questions**

**Q: Why Next.js instead of plain React?**
A: Next.js handles routing, building, optimization automatically. Less config, more coding.

**Q: Why Shadcn/UI instead of Material-UI?**
A: You own the code. Can modify anything. No dependency bloat. Modern styling with Tailwind.

**Q: Can I test frontend without backend?**
A: Yes! UI will work, just won't have real data. Good for learning component behavior.

**Q: How do I debug WebSocket issues?**
A: Browser DevTools → Network tab → WS filter. See all WebSocket messages.

**Q: What if I want to change styling?**
A: Everything uses Tailwind classes. Change `className` prop. Example: `className="bg-blue-500"` → `className="bg-red-500"`

---

This guide teaches you **why** things work this way, not just **what** to do. Work through it with Claude Code, and you'll understand the full architecture!
