// components/FileUploadPanel.tsx
// File upload and management panel with processing status

import React, { useState, useRef, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Progress } from './ui/progress';
import { ScrollArea } from './ui/scroll-area';
import {
  Upload,
  File,
  FileText,
  FileVideo,
  FileAudio,
  FileImage,
  FileCode,
  Database,
  Archive,
  X,
  Eye,
  Download,
  CheckCircle,
  AlertCircle,
  Clock,
  RefreshCw
} from 'lucide-react';

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  uploadedAt: string;
  status: 'uploading' | 'processing' | 'complete' | 'failed';
  progress?: number;
  extractedText?: string;
  thumbnail?: string;
  error?: string;
  conversationId?: string;
}

interface FileUploadPanelProps {
  onFileSelect?: (files: FileList) => void;
  maxFileSize?: number; // in MB
  allowedTypes?: string[];
}

const FileUploadPanel: React.FC<FileUploadPanelProps> = ({
  onFileSelect,
  maxFileSize = 100, // 100MB default
  allowedTypes = ['*'] // all types by default
}) => {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const getFileIcon = (fileName: string, mimeType: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase() || '';

    // Video files
    if (['mp4', 'avi', 'mkv', 'mov'].includes(ext) || mimeType.startsWith('video/'))
      return <FileVideo className="h-4 w-4 text-purple-500" />;

    // Audio files
    if (['mp3', 'wav', 'flac', 'ogg'].includes(ext) || mimeType.startsWith('audio/'))
      return <FileAudio className="h-4 w-4 text-green-500" />;

    // Image files
    if (['jpg', 'jpeg', 'png', 'gif', 'svg'].includes(ext) || mimeType.startsWith('image/'))
      return <FileImage className="h-4 w-4 text-blue-500" />;

    // Code files
    if (['py', 'js', 'ts', 'html', 'css', 'cpp', 'java'].includes(ext))
      return <FileCode className="h-4 w-4 text-orange-500" />;

    // Data files
    if (['json', 'csv', 'xml', 'sql'].includes(ext))
      return <Database className="h-4 w-4 text-indigo-500" />;

    // Archive files
    if (['zip', 'tar', 'gz', 'rar'].includes(ext))
      return <Archive className="h-4 w-4 text-gray-500" />;

    // Document files
    if (['pdf', 'doc', 'docx', 'txt', 'md'].includes(ext))
      return <FileText className="h-4 w-4 text-red-500" />;

    return <File className="h-4 w-4 text-gray-500" />;
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'complete': return 'text-green-600';
      case 'processing': return 'text-blue-600';
      case 'uploading': return 'text-yellow-600';
      case 'failed': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'complete': return <CheckCircle className="h-3 w-3" />;
      case 'processing': return <RefreshCw className="h-3 w-3 animate-spin" />;
      case 'uploading': return <Clock className="h-3 w-3" />;
      case 'failed': return <AlertCircle className="h-3 w-3" />;
      default: return null;
    }
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFiles = e.dataTransfer.files;
    handleFiles(droppedFiles);
  }, []);

  const handleFiles = (fileList: FileList) => {
    const newFiles: UploadedFile[] = [];

    Array.from(fileList).forEach(file => {
      // Check file size
      if (file.size > maxFileSize * 1024 * 1024) {
        alert(`File ${file.name} exceeds maximum size of ${maxFileSize}MB`);
        return;
      }

      // Check file type if restrictions exist
      if (allowedTypes[0] !== '*') {
        const fileExt = file.name.split('.').pop()?.toLowerCase();
        if (!fileExt || !allowedTypes.includes(fileExt)) {
          alert(`File type .${fileExt} not allowed`);
          return;
        }
      }

      // Create file entry
      const uploadedFile: UploadedFile = {
        id: `file-${Date.now()}-${Math.random()}`,
        name: file.name,
        size: file.size,
        type: file.type || 'unknown',
        uploadedAt: new Date().toISOString(),
        status: 'uploading',
        progress: 0
      };

      newFiles.push(uploadedFile);

      // TODO: Replace with actual API call when backend is connected
      // This simulation shows how the UI will behave during real uploads
      simulateFileProcessing(uploadedFile);
    });

    setFiles(prev => [...prev, ...newFiles]);

    if (onFileSelect) {
      onFileSelect(fileList);
    }
  };

  const simulateFileProcessing = (file: UploadedFile) => {
    // TEMPORARY: Simulates upload/processing for UI testing
    // Replace with actual endpoint calls:
    // 1. POST /upload for file upload with progress tracking
    // 2. WebSocket updates for processing status
    // 3. GET /files/{id}/status for completion check

    // Simulate upload progress
    let progress = 0;
    const uploadInterval = setInterval(() => {
      progress += Math.random() * 30;
      if (progress >= 100) {
        clearInterval(uploadInterval);

        // Update to processing
        setFiles(prev => prev.map(f =>
          f.id === file.id
            ? { ...f, status: 'processing' as const, progress: 100 }
            : f
        ));

        // Simulate processing completion
        setTimeout(() => {
          setFiles(prev => prev.map(f =>
            f.id === file.id
              ? {
                  ...f,
                  status: 'complete' as const,
                  extractedText: 'Sample extracted text from file...'
                }
              : f
          ));
        }, 2000);
      } else {
        setFiles(prev => prev.map(f =>
          f.id === file.id
            ? { ...f, progress: Math.min(progress, 99) }
            : f
        ));
      }
    }, 200);
  };

  const removeFile = (fileId: string) => {
    setFiles(prev => prev.filter(f => f.id !== fileId));
    if (selectedFile === fileId) {
      setSelectedFile(null);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      handleFiles(e.target.files);
    }
  };

  // Group files by status for summary
  const filesByStatus = {
    uploading: files.filter(f => f.status === 'uploading').length,
    processing: files.filter(f => f.status === 'processing').length,
    complete: files.filter(f => f.status === 'complete').length,
    failed: files.filter(f => f.status === 'failed').length
  };

  const totalSize = files.reduce((sum, file) => sum + file.size, 0);

  return (
    <div className="space-y-4">
      {/* Upload Area */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Upload Files</CardTitle>
        </CardHeader>
        <CardContent>
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              isDragging
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-300 hover:border-gray-400'
            }`}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <Upload className="h-12 w-12 mx-auto mb-4 text-gray-400" />
            <p className="text-sm text-gray-600 mb-2">
              Drag and drop files here, or click to browse
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={handleFileInputChange}
              className="hidden"
              accept={allowedTypes[0] === '*' ? undefined : allowedTypes.join(',')}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
            >
              Select Files
            </Button>
            <p className="text-xs text-gray-500 mt-2">
              Maximum file size: {maxFileSize}MB
            </p>
          </div>

          {/* File Summary */}
          {files.length > 0 && (
            <div className="mt-4 p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-600">
                  {files.length} file{files.length !== 1 ? 's' : ''} • {formatFileSize(totalSize)}
                </span>
                <div className="flex gap-2">
                  {filesByStatus.uploading > 0 && (
                    <Badge variant="secondary" className="text-xs">
                      {filesByStatus.uploading} uploading
                    </Badge>
                  )}
                  {filesByStatus.processing > 0 && (
                    <Badge variant="secondary" className="text-xs">
                      {filesByStatus.processing} processing
                    </Badge>
                  )}
                  {filesByStatus.failed > 0 && (
                    <Badge variant="destructive" className="text-xs">
                      {filesByStatus.failed} failed
                    </Badge>
                  )}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* File List */}
      {files.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Uploaded Files</CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-64">
              <div className="space-y-2">
                {files.map(file => (
                  <div
                    key={file.id}
                    className={`p-3 rounded-lg border transition-all cursor-pointer ${
                      selectedFile === file.id
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:bg-gray-50'
                    }`}
                    onClick={() => setSelectedFile(
                      selectedFile === file.id ? null : file.id
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 flex-1">
                        {getFileIcon(file.name, file.type)}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{file.name}</p>
                          <p className="text-xs text-gray-500">
                            {formatFileSize(file.size)} • {new Date(file.uploadedAt).toLocaleTimeString()}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <div className={`flex items-center gap-1 text-xs ${getStatusColor(file.status)}`}>
                          {getStatusIcon(file.status)}
                          <span>{file.status}</span>
                        </div>

                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            removeFile(file.id);
                          }}
                          className="h-6 w-6 p-0"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    {/* Progress bar for uploading/processing */}
                    {(file.status === 'uploading' || file.status === 'processing') && file.progress !== undefined && (
                      <Progress value={file.progress} className="h-1 mt-2" />
                    )}

                    {/* Expanded details */}
                    {selectedFile === file.id && file.status === 'complete' && (
                      <div className="mt-3 pt-3 border-t border-gray-200">
                        {file.extractedText && (
                          <div className="text-xs text-gray-600 mb-2">
                            <p className="font-medium mb-1">Extracted Content:</p>
                            <p className="bg-gray-50 p-2 rounded">{file.extractedText}</p>
                          </div>
                        )}

                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" className="flex-1 h-7 text-xs">
                            <Eye className="h-3 w-3 mr-1" />
                            Preview
                          </Button>
                          <Button size="sm" variant="outline" className="flex-1 h-7 text-xs">
                            <Download className="h-3 w-3 mr-1" />
                            Download
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* Error message */}
                    {file.status === 'failed' && file.error && (
                      <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-600">
                        {file.error}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default FileUploadPanel;