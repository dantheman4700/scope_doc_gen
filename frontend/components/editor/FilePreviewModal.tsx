"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Loader2, Download, FileText, AlertCircle, ChevronLeft, ChevronRight } from "lucide-react";
import dynamic from "next/dynamic";

// Dynamic imports for heavy libraries
const Document = dynamic(() => import("react-pdf").then((mod) => mod.Document), { ssr: false });
const Page = dynamic(() => import("react-pdf").then((mod) => mod.Page), { ssr: false });

interface FilePreviewModalProps {
  file: {
    id: string;
    name: string;
    mediaType?: string;
    path?: string;
  } | null;
  projectId: string;
  onClose: () => void;
}

// PDF Preview Component
function PdfPreview({ url }: { url: string }) {
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [pdfError, setPdfError] = useState<string | null>(null);

  useEffect(() => {
    // Set up PDF.js worker
    import("react-pdf").then((pdfjs) => {
      pdfjs.pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.pdfjs.version}/build/pdf.worker.min.mjs`;
    });
  }, []);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
    setPageNumber(1);
  }

  function onDocumentLoadError(error: Error) {
    console.error("PDF load error:", error);
    setPdfError("Failed to load PDF");
  }

  if (pdfError) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4 text-muted-foreground">
        <AlertCircle className="h-12 w-12" />
        <p className="text-sm">{pdfError}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center">
      <Document
        file={url}
        onLoadSuccess={onDocumentLoadSuccess}
        onLoadError={onDocumentLoadError}
        loading={
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <Page 
          pageNumber={pageNumber} 
          width={700}
          renderTextLayer={false}
          renderAnnotationLayer={false}
        />
      </Document>
      {numPages > 1 && (
        <div className="flex items-center gap-4 mt-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
            disabled={pageNumber <= 1}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm">
            Page {pageNumber} of {numPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPageNumber((p) => Math.min(numPages, p + 1))}
            disabled={pageNumber >= numPages}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}

// DOCX Preview Component
function DocxPreview({ url }: { url: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [docxError, setDocxError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDocx() {
      if (!containerRef.current) return;
      
      try {
        const response = await fetch(url);
        if (!response.ok) throw new Error("Failed to fetch DOCX");
        
        const arrayBuffer = await response.arrayBuffer();
        const { renderAsync } = await import("docx-preview");
        
        await renderAsync(arrayBuffer, containerRef.current, undefined, {
          className: "docx-preview",
          inWrapper: true,
          ignoreWidth: false,
          ignoreHeight: false,
        });
        
        setLoading(false);
      } catch (err) {
        console.error("DOCX preview error:", err);
        setDocxError("Failed to preview DOCX file");
        setLoading(false);
      }
    }
    
    loadDocx();
  }, [url]);

  if (docxError) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4 text-muted-foreground">
        <AlertCircle className="h-12 w-12" />
        <p className="text-sm">{docxError}</p>
      </div>
    );
  }

  return (
    <div className="relative">
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/80">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}
      <div 
        ref={containerRef} 
        className="docx-container max-h-[60vh] overflow-auto bg-white p-4 rounded-lg"
        style={{ minHeight: "200px" }}
      />
    </div>
  );
}

// XLSX Preview Component
function XlsxPreview({ url }: { url: string }) {
  const [data, setData] = useState<{ columns: string[]; rows: Record<string, unknown>[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [xlsxError, setXlsxError] = useState<string | null>(null);
  const [sheetNames, setSheetNames] = useState<string[]>([]);
  const [activeSheet, setActiveSheet] = useState<string>("");
  // Store workbook in state so we can switch sheets
  const [workbook, setWorkbook] = useState<import("xlsx").WorkBook | null>(null);

  // Load sheet data from workbook - defined outside useEffect so it can be called from click handlers
  const loadSheet = useCallback(async (wb: import("xlsx").WorkBook, sheetName: string) => {
    const XLSX = await import("xlsx");
    const sheet = wb.Sheets[sheetName];
    // header: 1 returns array of arrays
    const jsonData = XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1 });
    
    if (jsonData.length === 0) {
      setData({ columns: [], rows: [] });
      return;
    }
    
    // First row as headers
    const firstRow = jsonData[0] as unknown[];
    const headers = firstRow.map((h, i) => String(h || `Column ${i + 1}`));
    const rows = jsonData.slice(1).map((row) => {
      const rowData: Record<string, unknown> = {};
      const rowArray = row as unknown[];
      rowArray.forEach((cell, i) => {
        rowData[headers[i] || `col${i}`] = cell;
      });
      return rowData;
    });
    
    setData({ columns: headers, rows });
  }, []);

  // Handle sheet tab click
  const handleSheetChange = useCallback((sheetName: string) => {
    setActiveSheet(sheetName);
    if (workbook) {
      loadSheet(workbook, sheetName);
    }
  }, [workbook, loadSheet]);

  useEffect(() => {
    async function loadXlsx() {
      try {
        const response = await fetch(url);
        if (!response.ok) throw new Error("Failed to fetch XLSX");
        
        const arrayBuffer = await response.arrayBuffer();
        const XLSX = await import("xlsx");
        
        const wb = XLSX.read(arrayBuffer, { type: "array" });
        setWorkbook(wb);
        setSheetNames(wb.SheetNames);
        
        const firstSheet = wb.SheetNames[0];
        setActiveSheet(firstSheet);
        
        // Load first sheet data
        const sheet = wb.Sheets[firstSheet];
        const jsonData = XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1 });
        
        if (jsonData.length > 0) {
          const firstRow = jsonData[0] as unknown[];
          const headers = firstRow.map((h, i) => String(h || `Column ${i + 1}`));
          const rows = jsonData.slice(1).map((row) => {
            const rowData: Record<string, unknown> = {};
            const rowArray = row as unknown[];
            rowArray.forEach((cell, i) => {
              rowData[headers[i] || `col${i}`] = cell;
            });
            return rowData;
          });
          setData({ columns: headers, rows });
        } else {
          setData({ columns: [], rows: [] });
        }
        
        setLoading(false);
      } catch (err) {
        console.error("XLSX preview error:", err);
        setXlsxError("Failed to preview XLSX file");
        setLoading(false);
      }
    }
    
    loadXlsx();
  }, [url]);

  if (xlsxError) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4 text-muted-foreground">
        <AlertCircle className="h-12 w-12" />
        <p className="text-sm">{xlsxError}</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!data) {
    return <div className="text-center text-muted-foreground">No data</div>;
  }

  return (
    <div className="flex flex-col gap-2">
      {sheetNames.length > 1 && (
        <div className="flex gap-2 flex-wrap">
          {sheetNames.map((name) => (
            <Button
              key={name}
              variant={activeSheet === name ? "default" : "outline"}
              size="sm"
              onClick={() => handleSheetChange(name)}
            >
              {name}
            </Button>
          ))}
        </div>
      )}
      <div className="overflow-auto max-h-[55vh] border rounded-lg">
        <table className="min-w-full text-xs">
          <thead className="bg-muted sticky top-0">
            <tr>
              {data.columns.map((col, i) => (
                <th key={i} className="px-3 py-2 text-left font-medium border-b">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.slice(0, 100).map((row, i) => (
              <tr key={i} className="hover:bg-muted/50">
                {data.columns.map((col, j) => (
                  <td key={j} className="px-3 py-1.5 border-b">
                    {String(row[col] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {data.rows.length > 100 && (
          <div className="p-2 text-center text-xs text-muted-foreground">
            Showing first 100 rows of {data.rows.length}
          </div>
        )}
      </div>
    </div>
  );
}

export function FilePreviewModal({ file, projectId, onClose }: FilePreviewModalProps) {
  const [content, setContent] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [fileType, setFileType] = useState<"image" | "text" | "pdf" | "docx" | "xlsx" | "unknown">("unknown");

  useEffect(() => {
    if (!file) {
      setContent(null);
      setError(null);
      setImageUrl(null);
      setFileUrl(null);
      setFileType("unknown");
      return;
    }

    const loadFileContent = async () => {
      setIsLoading(true);
      setError(null);
      setContent(null);
      setImageUrl(null);
      setFileUrl(null);

      const ext = file.name.toLowerCase().split(".").pop() || "";
      const downloadUrl = `/api/projects/${projectId}/files/${file.id}/download`;
      
      // Determine file type
      if (["jpg", "jpeg", "png", "gif", "webp", "svg"].includes(ext) || file.mediaType?.startsWith("image/")) {
        setFileType("image");
        try {
          const res = await fetch(downloadUrl);
          if (!res.ok) throw new Error("Failed to load image");
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          setImageUrl(url);
        } catch (err) {
          setError((err as Error).message);
        }
      } else if (ext === "pdf") {
        setFileType("pdf");
        setFileUrl(downloadUrl);
      } else if (["docx", "doc"].includes(ext)) {
        setFileType("docx");
        setFileUrl(downloadUrl);
      } else if (["xlsx", "xls"].includes(ext)) {
        setFileType("xlsx");
        setFileUrl(downloadUrl);
      } else if (["txt", "md", "csv", "json", "yaml", "yml", "xml", "html", "vtt"].includes(ext)) {
        setFileType("text");
        try {
          const res = await fetch(downloadUrl);
          if (!res.ok) throw new Error("Failed to load file");
          const text = await res.text();
          setContent(text);
        } catch (err) {
          setError((err as Error).message);
        }
      } else {
        setFileType("unknown");
        setError(`Preview not available for ${ext.toUpperCase()} files.`);
      }
      
      setIsLoading(false);
    };

    loadFileContent();

    // Cleanup
    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [file, projectId]);

  const handleDownload = () => {
    if (!file) return;
    window.open(`/api/projects/${projectId}/files/${file.id}/download`, "_blank");
  };

  if (!file) return null;

  return (
    <Dialog open={!!file} onOpenChange={() => onClose()}>
      <DialogContent className="max-w-5xl max-h-[85vh] flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <div className="flex items-center justify-between">
            <DialogTitle className="flex items-center gap-2 text-base">
              <FileText className="h-4 w-4" />
              {file.name}
            </DialogTitle>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleDownload}>
                <Download className="h-4 w-4 mr-1" />
                Download
              </Button>
            </div>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-auto min-h-0">
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-64 gap-4 text-muted-foreground">
              <AlertCircle className="h-12 w-12" />
              <p className="text-sm text-center">{error}</p>
              <Button variant="outline" onClick={handleDownload}>
                <Download className="h-4 w-4 mr-2" />
                Download File
              </Button>
            </div>
          ) : fileType === "image" && imageUrl ? (
            <div className="flex items-center justify-center p-4">
              <img 
                src={imageUrl} 
                alt={file.name}
                className="max-w-full max-h-[65vh] object-contain rounded-lg"
              />
            </div>
          ) : fileType === "pdf" && fileUrl ? (
            <PdfPreview url={fileUrl} />
          ) : fileType === "docx" && fileUrl ? (
            <DocxPreview url={fileUrl} />
          ) : fileType === "xlsx" && fileUrl ? (
            <XlsxPreview url={fileUrl} />
          ) : fileType === "text" && content ? (
            <pre className="p-4 bg-muted/50 rounded-lg text-xs font-mono whitespace-pre-wrap overflow-auto max-h-[65vh]">
              {content}
            </pre>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 gap-4 text-muted-foreground">
              <p>No preview available</p>
              <Button variant="outline" onClick={handleDownload}>
                <Download className="h-4 w-4 mr-2" />
                Download File
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
