import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useTenant } from './contexts/TenantContext';
import { MainLayout } from './components/Layout/MainLayout';
import { EnhancedQueryInterface } from './components/Query/EnhancedQueryInterface';
import { AuditLogViewer } from './components/Audit/AuditLogViewer';
import { ApiKeyModal } from './components/ApiKeyModal';
import { SyncDashboard } from './components/Sync/SyncDashboard';
import { RAGFloatingActions } from './components/ui/floating-action-button';
import { RAGDashboardStats } from './components/ui/stats-card';
import { AnimatedButton } from './components/ui/animated-button';
import { Toaster } from "@/components/ui/toaster";
import { TypingAnimation } from './components/ui/typing-animation';
import { Sparkles, Search, BarChart3, FileText, Zap } from 'lucide-react';
import './App.css';

type ActiveView = 'dashboard' | 'search' | 'sync' | 'audit';

function EnhancedApp() {
  const [activeView, setActiveView] = useState<ActiveView>('dashboard');
  const { apiKey, tenant } = useTenant();

  const handleViewChange = (view: ActiveView) => {
    setActiveView(view);
  };

  // If there's no API key, force the user to configure one.
  if (!apiKey) {
    return (
      <>
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
        >
          <ApiKeyModal />
        </motion.div>
        <Toaster />
      </>
    );
  }

  const tabs = [
    { id: 'dashboard', name: 'Dashboard', icon: BarChart3, color: 'from-blue-500 to-blue-600' },
    { id: 'search', name: 'Search', icon: Search, color: 'from-green-500 to-green-600' },
    { id: 'sync', name: 'Sync', icon: Zap, color: 'from-purple-500 to-purple-600' },
    { id: 'audit', name: 'Audit Log', icon: FileText, color: 'from-orange-500 to-orange-600' },
  ];

  const renderContent = () => {
    switch (activeView) {
      case 'dashboard':
        return (
          <motion.div
            key="dashboard"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.3 }}
            className="space-y-8"
          >
            <div className="text-center space-y-4">
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.2 }}
                className="mx-auto w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg"
              >
                <Sparkles className="text-white" size={32} />
              </motion.div>
              
              <div>
                <TypingAnimation 
                  text="Welcome to your intelligent document platform"
                  duration={2}
                  className="text-2xl font-bold text-gray-800"
                />
                <motion.p 
                  className="text-gray-600 mt-2"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 1.5 }}
                >
                  Ask questions, get insights, and manage your knowledge base
                </motion.p>
              </div>
            </div>
            
            <RAGDashboardStats />
            
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.8 }}
              className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-200"
            >
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Quick Actions</h3>
              <div className="flex flex-wrap gap-3">
                <AnimatedButton
                  variant="glow"
                  animation="bounce"
                  icon={<Search size={16} />}
                  onClick={() => handleViewChange('search')}
                >
                  Start Searching
                </AnimatedButton>
                <AnimatedButton
                  variant="outline"
                  animation="slide"
                  icon={<Zap size={16} />}
                  onClick={() => handleViewChange('sync')}
                >
                  Sync Documents
                </AnimatedButton>
                <AnimatedButton
                  variant="ghost"
                  animation="wiggle"
                  icon={<FileText size={16} />}
                  onClick={() => handleViewChange('audit')}
                >
                  View Logs
                </AnimatedButton>
              </div>
            </motion.div>
          </motion.div>
        );
      case 'search':
        return (
          <motion.div
            key="search"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.3 }}
          >
            <EnhancedQueryInterface />
          </motion.div>
        );
      case 'sync':
        return (
          <motion.div
            key="sync"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.3 }}
          >
            <SyncDashboard />
          </motion.div>
        );
      case 'audit':
        return (
          <motion.div
            key="audit"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.3 }}
          >
            <AuditLogViewer />
          </motion.div>
        );
      default:
        return null;
    }
  };

  return (
    <>
      <MainLayout>
        <motion.div 
          className="mb-8"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex items-center gap-3 mb-2">
            <motion.div
              className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg"
              animate={{ rotate: [0, 5, -5, 0] }}
              transition={{ duration: 2, repeat: Infinity, repeatDelay: 3 }}
            >
              <Sparkles className="text-white" size={24} />
            </motion.div>
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                RAG Platform
              </h1>
              <motion.p 
                className="text-lg text-gray-500 mt-1"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
              >
                Selected Tenant: 
                <span className="font-semibold text-blue-600 ml-1">
                  {tenant || 'None'}
                </span>
              </motion.p>
            </div>
          </div>
        </motion.div>

        {/* Enhanced Tab Navigation */}
        <motion.div 
          className="mb-8"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <nav className="flex space-x-2 bg-gray-100 p-2 rounded-xl" aria-label="Tabs">
            {tabs.map((tab, index) => {
              const Icon = tab.icon;
              const isActive = activeView === tab.id;
              
              return (
                <motion.button
                  key={tab.id}
                  onClick={() => handleViewChange(tab.id as ActiveView)}
                  className={`
                    relative flex items-center gap-2 px-4 py-3 font-medium text-sm rounded-lg transition-all duration-200
                    ${isActive
                      ? 'bg-white text-gray-900 shadow-md'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-white/50'
                    }
                  `}
                  disabled={!tenant}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1 }}
                >
                  {isActive && (
                    <motion.div
                      className={`absolute inset-0 bg-gradient-to-r ${tab.color} opacity-10 rounded-lg`}
                      layoutId="activeTab"
                      transition={{ type: "spring", stiffness: 400, damping: 30 }}
                    />
                  )}
                  
                  <motion.div
                    className={isActive ? `text-transparent bg-gradient-to-r ${tab.color} bg-clip-text` : ''}
                    animate={{ rotate: isActive ? [0, 10, -10, 0] : 0 }}
                    transition={{ duration: 0.6 }}
                  >
                    <Icon size={18} />
                  </motion.div>
                  
                  <span className={isActive ? `text-transparent bg-gradient-to-r ${tab.color} bg-clip-text font-semibold` : ''}>
                    {tab.name}
                  </span>
                </motion.button>
              );
            })}
          </nav>
        </motion.div>

        {/* Content Area */}
        <motion.div 
          className="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden"
          layout
        >
          <AnimatePresence mode="wait">
            <div className="p-6 min-h-[500px]">
              {tenant ? (
                renderContent()
              ) : (
                <motion.div 
                  className="text-center py-16"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                >
                  <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <FileText className="text-gray-400" size={24} />
                  </div>
                  <TypingAnimation 
                    text="Please select a tenant to begin your journey"
                    duration={2}
                    className="text-gray-500 text-lg"
                  />
                </motion.div>
              )}
            </div>
          </AnimatePresence>
        </motion.div>
      </MainLayout>

      {/* Floating Action Button */}
      <RAGFloatingActions />
      
      <Toaster />
    </>
  );
}

export default EnhancedApp;