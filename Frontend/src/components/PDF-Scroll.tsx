import { useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { FileText } from 'lucide-react';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PDFScrollProps {
    file: string;
    height?: string;
    width?: number;
}

export function PDFScroll({ file, height = '40vh', width = 600 }: PDFScrollProps) {
    const [numPages, setNumPages] = useState<number | null>(null);

    function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
        setNumPages(numPages);
    }

    return (
        <div
            className="overflow-y-auto scroll-smooth bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-900 dark:to-slate-800 rounded-lg"
            style={{ height }}
        >
            <div className="p-4">
                <Document
                    file={file}
                    onLoadSuccess={onDocumentLoadSuccess}
                    loading={
                        <div className="flex items-center justify-center py-20">
                            <div className="text-center">
                                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-3"></div>
                                <p className="text-sm text-muted-foreground">Loading report...</p>
                            </div>
                        </div>
                    }
                    error={
                        <div className="flex items-center justify-center py-20">
                            <div className="text-center">
                                <FileText className="w-16 h-16 mx-auto mb-3 text-muted-foreground" />
                                <p className="text-sm text-muted-foreground">Unable to load report</p>
                            </div>
                        </div>
                    }
                    className="flex flex-col items-center gap-4"
                >
                    {numPages && Array.from({ length: numPages }, (_, index) => (
                        <div key={index} className="bg-white shadow-lg rounded overflow-hidden">
                            <Page
                                pageNumber={index + 1}
                                width={width}
                                renderTextLayer={true}
                                renderAnnotationLayer={true}
                                className="transition-opacity duration-300"
                            />
                            <div className="text-center py-2 bg-slate-100 dark:bg-slate-800 text-xs text-muted-foreground">
                                Page {index + 1} of {numPages}
                            </div>
                        </div>
                    ))}
                </Document>
            </div>
        </div>
    );
}
