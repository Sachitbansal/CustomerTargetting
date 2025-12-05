import { motion } from 'motion/react';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { TrendingUp, Users, Phone, CheckCircle, XCircle, Clock } from 'lucide-react';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

export function ModelStats() {
  // Mock data for recommended users vs time
  const timeSeriesData = [
    { time: '9 AM', carLoans: 45, mutualFunds: 32, nifty: 28, others: 15 },
    { time: '10 AM', carLoans: 52, mutualFunds: 38, nifty: 35, others: 22 },
    { time: '11 AM', carLoans: 48, mutualFunds: 45, nifty: 42, others: 28 },
    { time: '12 PM', carLoans: 65, mutualFunds: 52, nifty: 48, others: 35 },
    { time: '1 PM', carLoans: 58, mutualFunds: 48, nifty: 45, others: 30 },
    { time: '2 PM', carLoans: 72, mutualFunds: 62, nifty: 55, others: 42 },
    { time: '3 PM', carLoans: 68, mutualFunds: 58, nifty: 52, others: 38 },
    { time: '4 PM', carLoans: 55, mutualFunds: 48, nifty: 45, others: 32 },
  ];

  // Mock data for conversion rates
  const conversionData = [
    { name: 'Car Loans', value: 68, color: '#3b82f6' },
    { name: 'Mutual Funds', value: 72, color: '#8b5cf6' },
    { name: 'Nifty', value: 65, color: '#06b6d4' },
    { name: 'Others', value: 58, color: '#10b981' },
  ];

  // Mock data for call outcomes
  const callOutcomeData = [
    { category: 'Car Loans', success: 156, failed: 74, pending: 28 },
    { category: 'Mutual Funds', success: 189, failed: 56, pending: 18 },
    { category: 'Nifty', success: 142, failed: 68, pending: 32 },
    { category: 'Others', success: 98, failed: 45, pending: 22 },
  ];

  const categories = [
    {
      name: 'Car Loans',
      accuracy: '94.2%',
      predictions: 1247,
      conversions: 848,
      color: 'bg-blue-500',
      icon: '🚗',
    },
    {
      name: 'Mutual Funds',
      accuracy: '96.1%',
      predictions: 1586,
      conversions: 1142,
      color: 'bg-purple-500',
      icon: '💰',
    },
    {
      name: 'Nifty',
      accuracy: '92.8%',
      predictions: 968,
      conversions: 629,
      color: 'bg-cyan-500',
      icon: '📈',
    },
    {
      name: 'Others',
      accuracy: '89.5%',
      predictions: 542,
      conversions: 314,
      color: 'bg-green-500',
      icon: '📊',
    },
  ];

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
            <h1 className="mb-2">Model Statistics</h1>
            <p className="text-muted-foreground">
              Real-time performance metrics and AI predictions across all targeted calling campaigns
            </p>
          </motion.div>

          {/* Overall Metrics */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.5 }}
            className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8"
          >
            {[
              { label: 'Total Predictions', value: '4,343', icon: TrendingUp, color: 'text-blue-500' },
              { label: 'Active Users', value: '2,933', icon: Users, color: 'text-purple-500' },
              { label: 'Calls Completed', value: '3,247', icon: Phone, color: 'text-cyan-500' },
              { label: 'Avg Accuracy', value: '93.2%', icon: CheckCircle, color: 'text-green-500' },
            ].map((metric, index) => {
              const Icon = metric.icon;
              return (
                <motion.div
                  key={metric.label}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.2 + index * 0.1, duration: 0.3 }}
                >
                  <Card className="p-6 hover:shadow-lg transition-shadow">
                    <div className="flex items-center justify-between mb-2">
                      <Icon className={`w-8 h-8 ${metric.color}`} />
                      <Badge variant="secondary">{metric.value}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{metric.label}</p>
                  </Card>
                </motion.div>
              );
            })}
          </motion.div>

          {/* Graphs Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="mb-8"
          >
            <h2 className="mb-4">Recommended Users vs Time</h2>
            <Card className="p-6">
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={timeSeriesData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="time" stroke="var(--foreground)" />
                  <YAxis stroke="var(--foreground)" />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'var(--card)', 
                      border: '1px solid var(--border)',
                      borderRadius: '8px'
                    }} 
                  />
                  <Legend />
                  <Line type="monotone" dataKey="carLoans" stroke="#3b82f6" name="Car Loans" strokeWidth={2} />
                  <Line type="monotone" dataKey="mutualFunds" stroke="#8b5cf6" name="Mutual Funds" strokeWidth={2} />
                  <Line type="monotone" dataKey="nifty" stroke="#06b6d4" name="Nifty" strokeWidth={2} />
                  <Line type="monotone" dataKey="others" stroke="#10b981" name="Others" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          </motion.div>

          {/* Conversion Rates and Call Outcomes */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4, duration: 0.5 }}
            >
              <h3 className="mb-4">Conversion Rates by Category</h3>
              <Card className="p-6">
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={conversionData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, value }) => `${name}: ${value}%`}
                      outerRadius={100}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {conversionData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </Card>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4, duration: 0.5 }}
            >
              <h3 className="mb-4">Call Outcomes</h3>
              <Card className="p-6">
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={callOutcomeData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="category" stroke="var(--foreground)" />
                    <YAxis stroke="var(--foreground)" />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: 'var(--card)', 
                        border: '1px solid var(--border)',
                        borderRadius: '8px'
                      }} 
                    />
                    <Legend />
                    <Bar dataKey="success" fill="#22c55e" name="Success" />
                    <Bar dataKey="failed" fill="#ef4444" name="Failed" />
                    <Bar dataKey="pending" fill="#f59e0b" name="Pending" />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </motion.div>
          </div>

          {/* Category Performance */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.5 }}
          >
            <h2 className="mb-4">Category Performance</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {categories.map((category, index) => (
                <motion.div
                  key={category.name}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.6 + index * 0.1, duration: 0.3 }}
                  whileHover={{ scale: 1.05 }}
                >
                  <Card className="p-6 hover:shadow-xl transition-all border-t-4" style={{ borderTopColor: category.color.replace('bg-', '#') }}>
                    <div className="text-4xl mb-3">{category.icon}</div>
                    <h3 className="mb-4">{category.name}</h3>
                    
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">Accuracy</span>
                        <Badge className="bg-green-500 text-white">{category.accuracy}</Badge>
                      </div>
                      
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">Predictions</span>
                        <span className="text-sm">{category.predictions.toLocaleString()}</span>
                      </div>
                      
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">Conversions</span>
                        <span className="text-sm">{category.conversions.toLocaleString()}</span>
                      </div>

                      <div className="pt-3 border-t border-border">
                        <div className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-1 text-green-500">
                            <CheckCircle className="w-3 h-3" />
                            <span>{Math.round((category.conversions / category.predictions) * 100)}%</span>
                          </div>
                          <div className="flex items-center gap-1 text-muted-foreground">
                            <Clock className="w-3 h-3" />
                            <span>Live</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </Card>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* AI Agent Output Summary */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7, duration: 0.5 }}
            className="mt-8"
          >
            <h2 className="mb-4">AI Agent Call Output Summary</h2>
            <Card className="p-6 bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                    <CheckCircle className="w-6 h-6 text-green-500" />
                  </div>
                  <div>
                    <p className="text-2xl mb-1">2,933</p>
                    <p className="text-sm text-muted-foreground">Successful Agreements</p>
                    <p className="text-xs text-muted-foreground mt-1">67.6% success rate</p>
                  </div>
                </div>

                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0">
                    <XCircle className="w-6 h-6 text-red-500" />
                  </div>
                  <div>
                    <p className="text-2xl mb-1">1,243</p>
                    <p className="text-sm text-muted-foreground">Declined Offers</p>
                    <p className="text-xs text-muted-foreground mt-1">28.6% decline rate</p>
                  </div>
                </div>

                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-full bg-orange-500/20 flex items-center justify-center flex-shrink-0">
                    <Clock className="w-6 h-6 text-orange-500" />
                  </div>
                  <div>
                    <p className="text-2xl mb-1">167</p>
                    <p className="text-sm text-muted-foreground">Follow-up Required</p>
                    <p className="text-xs text-muted-foreground mt-1">3.8% pending</p>
                  </div>
                </div>
              </div>
            </Card>
          </motion.div>
        </div>
      </motion.div>
    </div>
  );
}
