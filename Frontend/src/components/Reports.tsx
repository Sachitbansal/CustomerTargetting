import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Card } from './ui/card';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { ReportCard } from './ReportCard';
import { ReportModal } from './ReportModal';
import { Search, TrendingUp, Wallet, LineChart, MoreHorizontal, Loader2, Wifi } from 'lucide-react';
import { getReports, Report as ApiReport } from '../services/api';
import { io, Socket } from 'socket.io-client';

type Category = 'carLoans' | 'mutualFunds' | 'nifty' | 'others';

interface Report {
  id: string;
  batchId: string;
  category: Category;
  userIds: string[];
  timestamp: Date;
  totalCalls: number;
  successfulCalls: number;
  reportFile?: string | null;
}

// Transform API response to frontend Report format
const transformReport = (apiReport: ApiReport): Report => ({
  id: apiReport.id,
  batchId: apiReport.batch_id,
  category: apiReport.category_id as Category,
  userIds: apiReport.userIds,
  timestamp: new Date(apiReport.timestamp),
  totalCalls: apiReport.total_calls,
  successfulCalls: apiReport.successful_calls,
  reportFile: apiReport.report_file,
});

export function Reports() {
  const [selectedCategory, setSelectedCategory] = useState<Category>('carLoans');
  const [searchQuery, setSearchQuery] = useState('');
  const [timeFilter, setTimeFilter] = useState('all');
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  const categories = [
    { id: 'carLoans' as Category, label: 'Car Loans', icon: <TrendingUp className="w-4 h-4" /> },
    { id: 'mutualFunds' as Category, label: 'Mutual Funds', icon: <Wallet className="w-4 h-4" /> },
    { id: 'nifty' as Category, label: 'Nifty', icon: <LineChart className="w-4 h-4" /> },
    { id: 'others' as Category, label: 'Others', icon: <MoreHorizontal className="w-4 h-4" /> },
  ];

  // Fetch reports when category changes
  useEffect(() => {
    const fetchReports = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getReports(selectedCategory);
        setReports(data.map(transformReport));
      } catch (err) {
        console.error('Failed to fetch reports:', err);
        setError('Failed to load reports. Make sure the backend is running.');
      } finally {
        setLoading(false);
      }
    };

    fetchReports();
  }, [selectedCategory]);

  // WebSocket connection for real-time updates
  useEffect(() => {
    const socket: Socket = io('http://localhost:5000', {
      transports: ['websocket', 'polling'],
    });

    socket.on('connect', () => {
      console.log('✅ Connected to WebSocket');
      setIsConnected(true);
    });

    socket.on('disconnect', () => {
      console.log('❌ Disconnected from WebSocket');
      setIsConnected(false);
    });

    socket.on('customer_update', async (data: any) => {
      console.log('🔔 Received customer update:', data);

      const { is_new_report, report, category, customer } = data;

      setLastUpdate(customer?.user_id || 'Unknown');

      // Only process if it's for the current category
      if (category === selectedCategory) {
        if (is_new_report) {
          // New batch created - add it instantly with animation
          console.log('✨ New batch created:', report.batch_id);

          const newReport: Report = {
            id: report.id,
            batchId: report.batch_id,
            category: report.category_id as Category,
            userIds: report.userIds || [],
            timestamp: new Date(report.timestamp),
            totalCalls: report.total_calls,
            successfulCalls: report.successful_calls,
            reportFile: report.report_file,
          };

          // Add to the beginning of the reports array
          setReports(prev => [newReport, ...prev]);

        } else {
          // Update existing batch
          console.log('🔄 Updating batch:', report.batch_id);

          setReports(prev => prev.map(r => {
            if (r.id === report.id) {
              return {
                ...r,
                userIds: report.userIds || [],
                totalCalls: report.total_calls,
                successfulCalls: report.successful_calls,
                timestamp: new Date(report.timestamp),
              };
            }
            return r;
          }));
        }
      }
    });

    return () => {
      socket.disconnect();
    };
  }, [selectedCategory]);

  const filteredReports = reports.filter(report => {
    // Search filter
    const matchesSearch = searchQuery === '' ||
      report.userIds.some(id => id.toLowerCase().includes(searchQuery.toLowerCase())) ||
      report.batchId.toLowerCase().includes(searchQuery.toLowerCase());

    // Time filter
    const now = Date.now();
    const reportTime = report.timestamp.getTime();
    let matchesTime = true;

    if (timeFilter === '1hour') {
      matchesTime = now - reportTime <= 60 * 60 * 1000;
    } else if (timeFilter === '1day') {
      matchesTime = now - reportTime <= 24 * 60 * 60 * 1000;
    } else if (timeFilter === '3days') {
      matchesTime = now - reportTime <= 3 * 24 * 60 * 60 * 1000;
    } else if (timeFilter === '7days') {
      matchesTime = now - reportTime <= 7 * 24 * 60 * 60 * 1000;
    }

    return matchesSearch && matchesTime;
  });

  return (
    <div className="min-h-screen p-8 overflow-auto">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5 }}
      >
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="mb-8"
          >
            <div className="flex items-start justify-between">
              <div>
                <h1 className="mb-2">Reports</h1>
                <p className="text-muted-foreground">
                  Batch reports for targeted calling campaigns with detailed user insights
                </p>
              </div>

              {/* Real-time status indicator */}
              <div className="flex items-center gap-2 px-4 py-2 rounded-lg border bg-card">
                <Wifi className={`w-4 h-4 ${isConnected ? 'text-green-500' : 'text-red-500'}`} />
                <div className="flex flex-col">
                  <span className="text-xs font-medium">
                    {isConnected ? '🟢 Live Updates' : '🔴 Offline'}
                  </span>
                  {lastUpdate && (
                    <span className="text-xs text-muted-foreground">
                      Last: {lastUpdate}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </motion.div>

          {/* Floating Category Navbar */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.5 }}
            className="sticky top-0 z-10 mb-8"
          >
            <Card className="p-2 bg-card/95 backdrop-blur-lg shadow-lg border-2">
              <div className="flex items-center gap-2 relative">
                {categories.map((category) => (
                  <motion.button
                    key={category.id}
                    onClick={() => setSelectedCategory(category.id)}
                    className={`
                      flex-1 px-6 py-3 rounded-lg transition-all duration-300 relative
                      ${selectedCategory === category.id
                        ? 'text-primary-foreground'
                        : 'text-foreground hover:bg-accent'
                      }
                    `}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    {selectedCategory === category.id && (
                      <motion.div
                        layoutId="activeCategory"
                        className="absolute inset-0 bg-primary rounded-lg shadow-lg"
                        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                      />
                    )}
                    <span className="relative z-10 flex items-center justify-center gap-2">
                      <span>{category.icon}</span>
                      <span>{category.label}</span>
                    </span>
                  </motion.button>
                ))}
              </div>
            </Card>
          </motion.div>

          {/* Filters */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="mb-6"
          >
            <Card className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="Search by User ID or Batch ID..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>

                <Select value={timeFilter} onValueChange={setTimeFilter}>
                  <SelectTrigger>
                    <SelectValue placeholder="Filter by time" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Time</SelectItem>
                    <SelectItem value="1hour">Last 1 Hour</SelectItem>
                    <SelectItem value="1day">Last 1 Day</SelectItem>
                    <SelectItem value="3days">Last 3 Days</SelectItem>
                    <SelectItem value="7days">Last 7 Days</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </Card>
          </motion.div>

          {/* Loading State */}
          {loading && (
            <div className="flex items-center justify-center py-20">
              <div className="text-center">
                <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
                <p className="text-muted-foreground">Loading reports...</p>
              </div>
            </div>
          )}

          {/* Error State */}
          {error && !loading && (
            <div className="text-center py-12">
              <p className="text-destructive mb-2">{error}</p>
              <p className="text-sm text-muted-foreground">
                Run <code className="bg-accent px-2 py-1 rounded">python app.py</code> in the Backend folder
              </p>
            </div>
          )}

          {/* Reports Grid */}
          {!loading && !error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3, duration: 0.5 }}
            >
              <AnimatePresence mode="wait">
                <motion.div
                  key={selectedCategory}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ duration: 0.3 }}
                  className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
                >
                  {filteredReports.map((report, index) => (
                    <motion.div
                      key={report.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05, duration: 0.3 }}
                    >
                      <ReportCard
                        report={report}
                        onOpen={() => setSelectedReport(report)}
                      />
                    </motion.div>
                  ))}
                </motion.div>
              </AnimatePresence>

              {filteredReports.length === 0 && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-center py-12"
                >
                  <p className="text-muted-foreground">No reports found matching your filters</p>
                </motion.div>
              )}
            </motion.div>
          )}
        </div>
      </motion.div>

      {/* Report Modal */}
      <ReportModal
        report={selectedReport}
        onClose={() => setSelectedReport(null)}
      />
    </div>
  );
}
