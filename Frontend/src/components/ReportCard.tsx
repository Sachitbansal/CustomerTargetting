import { useState } from 'react';
import { motion } from 'motion/react';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { FileText, Users, CheckCircle, Clock } from 'lucide-react';
import { Document, Page, pdfjs } from 'react-pdf';

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface Report {
  id: string;
  batchId: string;
  category: string;
  userIds: string[];
  timestamp: Date;
  totalCalls: number;
  successfulCalls: number;
}

interface ReportCardProps {
  report: Report;
  onOpen: () => void;
}

export function ReportCard({ report, onOpen }: ReportCardProps) {
  const successRate = Math.round((report.successfulCalls / report.totalCalls) * 100);
  const timeAgo = getTimeAgo(report.timestamp);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageLoaded, setPageLoaded] = useState(false);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
  }

  function onPageLoadSuccess() {
    setPageLoaded(true);
  }

  return (
    <motion.div
      whileHover={{ scale: 1.02, y: -5 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
    >
      <Card
        className="cursor-pointer hover:shadow-2xl transition-all duration-300 border-l-4 border-l-primary bg-card group overflow-hidden"
        onClick={onOpen}
      >
        {/* PDF Preview - Top 40% Only */}
        <div className="relative w-full bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-800 dark:to-slate-900 overflow-hidden h-[200px]">
          <div className="relative w-full h-full flex items-start justify-center overflow-hidden">
            {!pageLoaded && (
              <div className="absolute inset-0 flex items-center justify-center z-10">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
              </div>
            )}
            <Document
              file="/Report_exapmle.pdf"
              onLoadSuccess={onDocumentLoadSuccess}
              loading={
                <div className="h-full w-full flex items-center justify-center">
                  <div className="text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
                    <p className="text-xs text-muted-foreground">Loading PDF...</p>
                  </div>
                </div>
              }
              error={
                <div className="h-full w-full flex items-center justify-center p-4">
                  <div className="text-center">
                    <FileText className="w-12 h-12 mx-auto mb-2 text-muted-foreground" />
                    <p className="text-xs text-muted-foreground">Report Preview</p>
                  </div>
                </div>
              }
            >
              <Page
                pageNumber={1}
                onLoadSuccess={onPageLoadSuccess}
                width={350}
                renderTextLayer={false}
                renderAnnotationLayer={false}
                className={`transition-opacity duration-300 ${pageLoaded ? 'opacity-100' : 'opacity-0'}`}
              />
            </Document>
          </div>

          {/* Overlay gradients for better visual effect */}
          <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-black/70 via-black/30 to-transparent pointer-events-none"></div>
        </div>

        <div className="p-6">
          {/* Header */}
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                <FileText className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h4 className="text-sm font-semibold">{report.batchId}</h4>
                <p className="text-xs text-muted-foreground flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {timeAgo}
                </p>
              </div>
            </div>

            <Badge
              variant={successRate >= 70 ? 'default' : successRate >= 50 ? 'secondary' : 'destructive'}
              className="text-xs font-semibold"
            >
              {successRate}% Success
            </Badge>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-4 mb-4 pb-4 border-b border-border">
            <div>
              <p className="text-xs text-muted-foreground mb-1 font-medium">Total Calls</p>
              <p className="text-2xl font-bold">{report.totalCalls}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-1 font-medium">Successful</p>
              <p className="text-2xl font-bold flex items-center gap-1">
                {report.successfulCalls}
                <CheckCircle className="w-5 h-5 text-green-500" />
              </p>
            </div>
          </div>

          {/* User IDs Preview */}
          <div>
            <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1 font-medium">
              <Users className="w-3 h-3" />
              User IDs ({report.userIds.length})
            </p>
            <div className="flex flex-wrap gap-1">
              {report.userIds.slice(0, 3).map((userId) => (
                <Badge key={userId} variant="outline" className="text-xs font-mono">
                  {userId}
                </Badge>
              ))}
              {report.userIds.length > 3 && (
                <Badge variant="outline" className="text-xs font-semibold">
                  +{report.userIds.length - 3} more
                </Badge>
              )}
            </div>
          </div>

          {/* Hover hint */}
          <motion.div
            initial={{ opacity: 0 }}
            whileHover={{ opacity: 1 }}
            className="mt-4 pt-4 border-t border-border text-center"
          >
            <p className="text-xs text-primary font-medium">Click to view detailed report →</p>
          </motion.div>
        </div>
      </Card>
    </motion.div>
  );
}

function getTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);

  const intervals = {
    year: 31536000,
    month: 2592000,
    week: 604800,
    day: 86400,
    hour: 3600,
    minute: 60,
  };

  for (const [unit, secondsInUnit] of Object.entries(intervals)) {
    const interval = Math.floor(seconds / secondsInUnit);
    if (interval >= 1) {
      return `${interval} ${unit}${interval > 1 ? 's' : ''} ago`;
    }
  }

  return 'Just now';
}
