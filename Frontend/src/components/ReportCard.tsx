import { motion } from 'motion/react';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { FileText, Users, CheckCircle, Clock } from 'lucide-react';

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

  return (
    <motion.div
      whileHover={{ scale: 1.02, y: -5 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
    >
      <Card
        className="p-6 cursor-pointer hover:shadow-2xl transition-all duration-300 border-l-4 border-l-primary bg-card group"
        onClick={onOpen}
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
              <FileText className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h4 className="text-sm">{report.batchId}</h4>
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {timeAgo}
              </p>
            </div>
          </div>

          <Badge
            variant={successRate >= 70 ? 'default' : successRate >= 50 ? 'secondary' : 'destructive'}
            className="text-xs"
          >
            {successRate}% Success
          </Badge>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-4 mb-4 pb-4 border-b border-border">
          <div>
            <p className="text-xs text-muted-foreground mb-1">Total Calls</p>
            <p className="text-lg">{report.totalCalls}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-1">Successful</p>
            <p className="text-lg flex items-center gap-1">
              {report.successfulCalls}
              <CheckCircle className="w-4 h-4 text-green-500" />
            </p>
          </div>
        </div>

        {/* User IDs Preview */}
        <div>
          <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
            <Users className="w-3 h-3" />
            User IDs ({report.userIds.length})
          </p>
          <div className="flex flex-wrap gap-1">
            {report.userIds.slice(0, 3).map((userId) => (
              <Badge key={userId} variant="outline" className="text-xs">
                {userId}
              </Badge>
            ))}
            {report.userIds.length > 3 && (
              <Badge variant="outline" className="text-xs">
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
          <p className="text-xs text-primary">Click to view detailed report</p>
        </motion.div>
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
