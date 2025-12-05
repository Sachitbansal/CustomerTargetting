import { motion, AnimatePresence } from 'motion/react';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { X, Download, FileText, Phone, CheckCircle, XCircle, User, Calendar, Clock } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import { PDFScroll } from './PDF-Scroll';

interface Report {
  id: string;
  batchId: string;
  category: string;
  userIds: string[];
  timestamp: Date;
  totalCalls: number;
  successfulCalls: number;
}

interface ReportModalProps {
  report: Report | null;
  onClose: () => void;
}

// Generate mock user data
const generateUserData = (userId: string) => {
  const agreed = Math.random() > 0.35;
  const callDuration = Math.floor(Math.random() * 300) + 60; // 60-360 seconds

  return {
    userId,
    name: `Customer ${userId.split('-')[2]}`,
    agreed,
    callDuration,
    callDate: new Date(Date.now() - Math.random() * 24 * 60 * 60 * 1000),
    loanAmount: Math.floor(Math.random() * 500000) + 100000,
    creditScore: Math.floor(Math.random() * 200) + 650,
    riskLevel: agreed ? 'Low' : 'Medium',
  };
};

export function ReportModal({ report, onClose }: ReportModalProps) {
  if (!report) return null;

  const userData = report.userIds.map(generateUserData);

  return (
    <AnimatePresence>
      {report && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.9, opacity: 0, y: 20 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-5xl max-h-[90vh] overflow-auto"
          >
            <Card className="p-8 bg-card">
              {/* Header */}
              <div className="flex items-start justify-between mb-6 pb-6 border-b border-border">
                <div>
                  <h2 className="mb-2">{report.batchId}</h2>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Calendar className="w-4 h-4" />
                      {report.timestamp.toLocaleDateString()}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-4 h-4" />
                      {report.timestamp.toLocaleTimeString()}
                    </span>
                  </div>
                </div>

                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onClose}
                  className="hover:bg-destructive/10 hover:text-destructive"
                >
                  <X className="w-5 h-5" />
                </Button>
              </div>

              {/* Summary Stats */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                {[
                  { label: 'Total Users', value: report.userIds.length, icon: User, color: 'text-blue-500' },
                  { label: 'Agreed', value: report.successfulCalls, icon: CheckCircle, color: 'text-green-500' },
                  { label: 'Declined', value: report.totalCalls - report.successfulCalls, icon: XCircle, color: 'text-red-500' },
                  { label: 'Success Rate', value: `${Math.round((report.successfulCalls / report.totalCalls) * 100)}%`, icon: FileText, color: 'text-purple-500' },
                ].map((stat) => {
                  const Icon = stat.icon;
                  return (
                    <Card key={stat.label} className="p-4 bg-accent/50">
                      <div className="flex items-center gap-3">
                        <Icon className={`w-8 h-8 ${stat.color}`} />
                        <div>
                          <p className="text-2xl">{stat.value}</p>
                          <p className="text-xs text-muted-foreground">{stat.label}</p>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>

              {/* PDF Report Viewer - Fixed Height with Internal Scroll */}
              <div className="mb-6">
                <h3 className="mb-4 flex items-center gap-2">
                  <FileText className="w-5 h-5" />
                  Full Report
                </h3>
                <Card className="bg-accent/30 overflow-hidden">
                  <PDFScroll
                    file="/Report_exapmle.pdf"
                    height="40vh"
                    width={600}
                  />
                </Card>
              </div>

              {/* User Details */}
              <div>
                <h3 className="mb-4">User Details</h3>
                <div className="space-y-3">
                  {userData.map((user) => (
                    <TooltipProvider key={user.userId}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <motion.div
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            whileHover={{ scale: 1.01 }}
                            className="cursor-pointer"
                          >
                            <Card
                              className={`p-4 border-l-4 transition-all hover:shadow-lg ${user.agreed
                                ? 'border-l-green-500 bg-green-500/5'
                                : 'border-l-red-500 bg-red-500/5'
                                }`}
                            >
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4 flex-1">
                                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${user.agreed ? 'bg-green-500' : 'bg-red-500'
                                    }`}>
                                    {user.agreed ? (
                                      <CheckCircle className="w-5 h-5 text-white" />
                                    ) : (
                                      <XCircle className="w-5 h-5 text-white" />
                                    )}
                                  </div>

                                  <div className="flex-1">
                                    <div className="flex items-center gap-2 mb-1">
                                      <Badge variant="outline" className="text-xs">
                                        {user.userId}
                                      </Badge>
                                      <Badge
                                        variant={user.agreed ? 'default' : 'destructive'}
                                        className="text-xs"
                                      >
                                        {user.agreed ? 'Agreed' : 'Declined'}
                                      </Badge>
                                    </div>
                                    <p className="text-sm text-muted-foreground">
                                      {user.name} • {Math.floor(user.callDuration / 60)}m {user.callDuration % 60}s
                                    </p>
                                  </div>

                                  <div className="flex items-center gap-2">
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="gap-2"
                                      onClick={() => alert(`Generating detailed report for ${user.userId}`)}
                                    >
                                      <FileText className="w-4 h-4" />
                                      Detailed Report
                                    </Button>

                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="gap-2"
                                      onClick={() => alert(`Downloading call recording for ${user.userId}`)}
                                    >
                                      <Download className="w-4 h-4" />
                                      Recording
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            </Card>
                          </motion.div>
                        </TooltipTrigger>
                        <TooltipContent side="left" className="w-64 p-4">
                          <div className="space-y-2">
                            <div className="flex justify-between">
                              <span className="text-xs text-muted-foreground">Loan Amount:</span>
                              <span className="text-xs">₹{user.loanAmount.toLocaleString()}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-muted-foreground">Credit Score:</span>
                              <span className="text-xs">{user.creditScore}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-muted-foreground">Risk Level:</span>
                              <Badge variant="outline" className="text-xs h-5">
                                {user.riskLevel}
                              </Badge>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-xs text-muted-foreground">Call Date:</span>
                              <span className="text-xs">{user.callDate.toLocaleDateString()}</span>
                            </div>
                          </div>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  ))}
                </div>
              </div>

              {/* Footer Actions */}
              <div className="flex items-center justify-end gap-4 mt-6 pt-6 border-t border-border">
                <Button
                  variant="outline"
                  onClick={() => alert('Exporting batch report...')}
                  className="gap-2"
                >
                  <Download className="w-4 h-4" />
                  Export Batch Report
                </Button>
                <Button onClick={onClose}>
                  Close
                </Button>
              </div>
            </Card>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
