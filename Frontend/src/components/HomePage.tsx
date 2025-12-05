import { motion } from 'motion/react';
import { TrendingUp, Target, Brain, Phone, BarChart, Shield } from 'lucide-react';
import { Card } from './ui/card';

export function HomePage() {
  const features = [
    {
      icon: Brain,
      title: 'Agentic AI',
      description: 'Advanced AI agents that autonomously analyze customer data and make intelligent recommendations',
    },
    {
      icon: Target,
      title: 'Targeted Calling',
      description: 'Precision-based calling system that identifies high-probability conversion prospects',
    },
    {
      icon: TrendingUp,
      title: 'High Accuracy',
      description: 'Machine learning models with 94%+ accuracy in loan approval predictions',
    },
    {
      icon: Phone,
      title: 'Automated Outreach',
      description: 'AI-powered call automation with natural language processing for better engagement',
    },
    {
      icon: BarChart,
      title: 'Real-time Analytics',
      description: 'Live dashboard tracking conversion rates, call outcomes, and predictive insights',
    },
    {
      icon: Shield,
      title: 'Risk Assessment',
      description: 'Intelligent risk profiling using multi-factor analysis and behavioral patterns',
    },
  ];

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.5,
      },
    },
  };

  return (
    <div className="min-h-screen p-8 overflow-auto">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <div className="max-w-7xl mx-auto">
          {/* Hero Section */}
          <div className="mb-12 text-center">
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.5 }}
              className="inline-block mb-4"
            >
              <div className="px-6 py-2 bg-primary/10 text-primary rounded-full border-2 border-primary/20">
                <span className="text-sm uppercase tracking-wider">Demo Platform</span>
              </div>
            </motion.div>
            
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.6 }}
              className="mb-4"
            >
              AI-Powered Loan Prediction System
            </motion.h1>
            
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.6 }}
              className="text-muted-foreground max-w-3xl mx-auto text-lg"
            >
              Revolutionizing financial services with intelligent pathways for targeted calling,
              leveraging advanced AI agents to predict loan approvals with unprecedented accuracy
            </motion.p>
          </div>

          {/* Stats Banner */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.4, duration: 0.5 }}
            className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12"
          >
            {[
              { label: 'Prediction Accuracy', value: '94.2%', color: 'text-green-500' },
              { label: 'Active Campaigns', value: '12', color: 'text-blue-500' },
              { label: 'Calls Today', value: '1,247', color: 'text-purple-500' },
              { label: 'Conversion Rate', value: '68%', color: 'text-orange-500' },
            ].map((stat, index) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 + index * 0.1, duration: 0.5 }}
              >
                <Card className="p-6 text-center bg-card hover:shadow-xl transition-shadow duration-300 border-l-4 border-l-primary">
                  <p className={`text-3xl mb-2 ${stat.color}`}>{stat.value}</p>
                  <p className="text-sm text-muted-foreground">{stat.label}</p>
                </Card>
              </motion.div>
            ))}
          </motion.div>

          {/* Features Grid */}
          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
          >
            {features.map((feature, index) => {
              const Icon = feature.icon;
              return (
                <motion.div
                  key={feature.title}
                  variants={itemVariants}
                  whileHover={{ scale: 1.05, y: -5 }}
                  transition={{ type: 'spring', stiffness: 300 }}
                >
                  <Card className="p-6 h-full bg-card hover:shadow-2xl transition-all duration-300 border border-border hover:border-primary/50">
                    <motion.div
                      initial={{ rotate: 0 }}
                      whileHover={{ rotate: 360 }}
                      transition={{ duration: 0.6 }}
                      className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center mb-4"
                    >
                      <Icon className="w-6 h-6 text-primary" />
                    </motion.div>
                    <h3 className="mb-2">{feature.title}</h3>
                    <p className="text-muted-foreground text-sm">{feature.description}</p>
                  </Card>
                </motion.div>
              );
            })}
          </motion.div>

          {/* Overview Section */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1, duration: 0.6 }}
            className="mt-12"
          >
            <Card className="p-8 bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
              <h2 className="mb-4">System Overview</h2>
              <div className="space-y-4 text-muted-foreground">
                <p>
                  This demonstration platform showcases our cutting-edge Agentic AI technology designed
                  specifically for financial institutions. The system utilizes advanced machine learning
                  pathways to analyze customer data, predict loan approval probability, and orchestrate
                  targeted calling campaigns.
                </p>
                <p>
                  Our AI agents work autonomously to:
                </p>
                <ul className="list-disc list-inside space-y-2 ml-4">
                  <li>Analyze customer financial profiles and behavioral patterns</li>
                  <li>Predict loan approval likelihood with 94%+ accuracy</li>
                  <li>Prioritize leads based on conversion probability</li>
                  <li>Optimize call timing and agent allocation</li>
                  <li>Generate real-time insights and recommendations</li>
                </ul>
                <p className="pt-4 text-sm italic border-t border-border mt-6">
                  <strong>Note:</strong> This is a demonstration environment with simulated data.
                  All information displayed is for illustrative purposes only.
                </p>
              </div>
            </Card>
          </motion.div>
        </div>
      </motion.div>
    </div>
  );
}
