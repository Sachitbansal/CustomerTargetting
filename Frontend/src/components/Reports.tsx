import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Card } from './ui/card';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { ReportCard } from './ReportCard';
import { ReportModal } from './ReportModal';
import { Search, TrendingUp, Wallet, LineChart, MoreHorizontal } from 'lucide-react';

type Category = 'carLoans' | 'mutualFunds' | 'nifty' | 'others';

interface Report {
  id: string;
  batchId: string;
  category: Category;
  userIds: string[];
  timestamp: Date;
  totalCalls: number;
  successfulCalls: number;
}

const generateMockReports = (category: Category): Report[] => {
  const reports: Report[] = [];
  const categoryPrefixes = {
    carLoans: 'CL',
    mutualFunds: 'MF',
    nifty: 'NF',
    others: 'OT',
  };

  for (let i = 1; i <= 8; i++) {
    const userIds = Array.from({ length: 6 }, (_, j) =>
      `${categoryPrefixes[category]}-${String(i).padStart(3, '0')}-${String(j + 1).padStart(2, '0')}`
    );

    reports.push({
      id: `${category}-${i}`,
      batchId: `BATCH-${categoryPrefixes[category]}-${String(i).padStart(4, '0')}`,
      category,
      userIds,
      timestamp: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000),
      totalCalls: 6,
      successfulCalls: Math.floor(Math.random() * 4) + 2,
    });
  }

  return reports;
};

export function Reports() {
  const [selectedCategory, setSelectedCategory] = useState<Category>('carLoans');
  const [searchQuery, setSearchQuery] = useState('');
  const [timeFilter, setTimeFilter] = useState('all');
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);

  const categories = [
    { id: 'carLoans' as Category, label: 'Car Loans', icon: <TrendingUp className="w-4 h-4" /> },
    { id: 'mutualFunds' as Category, label: 'Mutual Funds', icon: <Wallet className="w-4 h-4" /> },
    { id: 'nifty' as Category, label: 'Nifty', icon: <LineChart className="w-4 h-4" /> },
    { id: 'others' as Category, label: 'Others', icon: <MoreHorizontal className="w-4 h-4" /> },
  ];

  const allReports = generateMockReports(selectedCategory);

  const filteredReports = allReports.filter(report => {
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
            <h1 className="mb-2">Reports</h1>
            <p className="text-muted-foreground">
              Batch reports for targeted calling campaigns with detailed user insights
            </p>
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

          {/* Reports Grid */}
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
