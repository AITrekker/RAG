import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Search, 
  BarChart3, 
  FileText, 
  Zap, 
  Sparkles, 
  MessageSquare, 
  Upload, 
  Settings,
  Send,
  Copy,
  ThumbsUp,
  Clock,
  Brain
} from 'lucide-react';

// Import our new interactive components
import { AnimatedButton } from './components/ui/animated-button';
import { FloatingActionButton } from './components/ui/floating-action-button';
import { TypingAnimation, StreamingText, LoadingDots } from './components/ui/typing-animation';
import { StatsCard } from './components/ui/stats-card';
import { AnimatedTabs, AnimatedTabContent } from './components/ui/animated-tabs';
import { ProgressBar, RAGLoadingStates, QuerySkeleton } from './components/ui/loading-states';
import { Toaster } from "@/components/ui/toaster";
import { useToast } from "@/components/ui/use-toast";
import { useTenant } from './contexts/TenantContext';
import { MainLayout } from './components/Layout/MainLayout';
import { ApiKeyModal } from './components/ApiKeyModal';
import './App.css';

type DemoView = 'dashboard' | 'search' | 'sync' | 'showcase';

function InteractiveDemo() {
  const [activeView, setActiveView] = useState<DemoView>('dashboard');
  const [isLoading, setIsLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [showResponse, setShowResponse] = useState(false);
  const { toast } = useToast();
  const { apiKey, tenant } = useTenant();

  // Simulate API call with loading states
  const handleQuery = async () => {
    if (!query.trim()) return;
    
    setIsLoading(true);
    setShowResponse(false);
    setResponse('');
    
    // Simulate processing steps
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    const mockResponse = `Based on your query "${query}", I found several relevant documents. Here's a comprehensive answer that addresses your question with specific examples and actionable insights. The information comes from multiple authoritative sources within your document collection.`;
    
    setResponse(mockResponse);
    setShowResponse(true);
    setIsLoading(false);
    
    toast({
      title: "Query Processed!",
      description: "Your question has been answered successfully.",
    });
  };

  // Simulate file upload
  const handleUpload = async () => {
    setUploadProgress(0);
    toast({
      title: "Upload Started",
      description: "Processing your documents...",
    });

    for (let i = 0; i <= 100; i += 10) {
      await new Promise(resolve => setTimeout(resolve, 200));
      setUploadProgress(i);
    }

    toast({
      title: "Upload Complete!",
      description: "3 documents processed successfully.",
    });
  };

  // Demo floating actions
  const floatingActions = [
    {
      id: "query",
      label: "New Query",
      icon: <MessageSquare size={20} />,
      onClick: () => setActiveView('search')
    },
    {
      id: "upload",
      label: "Upload Document",
      icon: <Upload size={20} />,
      onClick: handleUpload
    },
    {
      id: "settings",
      label: "Settings",
      icon: <Settings size={20} />,
      onClick: () => toast({ title: "Settings", description: "Settings panel opened!" })
    },
  ];

  // Tab configuration
  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: <BarChart3 size={18} />, color: 'from-blue-500 to-blue-600' },
    { id: 'search', label: 'Smart Search', icon: <Search size={18} />, color: 'from-green-500 to-green-600', badge: 3 },
    { id: 'sync', label: 'Sync Status', icon: <Zap size={18} />, color: 'from-purple-500 to-purple-600' },
    { id: 'showcase', label: 'Component Showcase', icon: <Sparkles size={18} />, color: 'from-orange-500 to-orange-600', badge: 'New' },
  ];

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

  const renderDashboard = () => (
    <motion.div
      key="dashboard"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="space-y-8"
    >
      {/* Hero Section */}
      <div className="text-center space-y-6">
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="mx-auto w-20 h-20 bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 rounded-3xl flex items-center justify-center shadow-xl"
        >
          <Sparkles className="text-white" size={40} />
        </motion.div>
        
        <div>
          <TypingAnimation 
            text="Welcome to the Interactive RAG Experience"
            duration={2.5}
            className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent"
          />
          <motion.p 
            className="text-gray-600 mt-4 text-lg max-w-2xl mx-auto"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 2.8 }}
          >
            Experience cutting-edge AI interactions with beautiful animations, smart feedback, and delightful micro-interactions
          </motion.p>
        </div>
      </div>

      {/* Stats Grid */}
      <motion.div 
        className="grid grid-cols-1 md:grid-cols-3 gap-6"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <StatsCard
          title="Total Queries"
          value={1247}
          change={{ value: 12, type: "increase" }}
          icon={<Brain size={24} />}
          color="blue"
          trend={[45, 52, 48, 61, 55, 67, 73, 82, 76, 89, 95, 88]}
          onClick={() => setActiveView('search')}
        />
        <StatsCard
          title="Documents Processed"
          value={342}
          change={{ value: 8, type: "increase" }}
          icon={<FileText size={24} />}
          color="green"
          trend={[12, 15, 18, 22, 19, 25, 28, 31, 29, 34, 37, 42]}
          onClick={() => setActiveView('sync')}
        />
        <StatsCard
          title="Response Time"
          value="1.2s"
          change={{ value: 5, type: "decrease" }}
          icon={<Clock size={24} />}
          color="purple"
          trend={[2.1, 1.9, 1.7, 1.5, 1.6, 1.4, 1.3, 1.2, 1.1, 1.2, 1.0, 1.2]}
          onClick={() => toast({ title: "Performance", description: "Optimized for speed!" })}
        />
      </motion.div>

      {/* Quick Actions */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        className="bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 rounded-2xl p-8 border border-blue-200"
      >
        <h3 className="text-xl font-bold text-gray-800 mb-6 flex items-center gap-2">
          <Zap className="text-blue-500" size={24} />
          Quick Actions
        </h3>
        <div className="flex flex-wrap gap-4">
          <AnimatedButton
            variant="glow"
            animation="bounce"
            icon={<Search size={16} />}
            onClick={() => setActiveView('search')}
            shimmer
          >
            Start AI Search
          </AnimatedButton>
          <AnimatedButton
            variant="premium"
            animation="slide"
            icon={<Upload size={16} />}
            onClick={handleUpload}
            badge={uploadProgress > 0 ? uploadProgress : undefined}
          >
            Upload Documents
          </AnimatedButton>
          <AnimatedButton
            variant="outline"
            animation="wiggle"
            icon={<Sparkles size={16} />}
            onClick={() => setActiveView('showcase')}
          >
            View Components
          </AnimatedButton>
        </div>
      </motion.div>
    </motion.div>
  );

  const renderSearch = () => (
    <motion.div
      key="search"
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      {/* Query Interface */}
      <div className="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
        <div className="bg-gradient-to-r from-blue-500 to-purple-600 p-6 text-white">
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Brain size={28} />
            AI-Powered Search
          </h2>
          <TypingAnimation 
            text="Ask anything about your documents..."
            duration={2}
            className="text-blue-100 mt-2"
          />
        </div>
        
        <div className="p-6 space-y-4">
          <div className="relative">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="What would you like to know?"
              className="w-full h-32 p-4 border-2 border-gray-200 rounded-lg focus:border-blue-500 transition-colors resize-none"
              disabled={isLoading}
            />
            <motion.button
              onClick={handleQuery}
              disabled={isLoading || !query.trim()}
              className="absolute bottom-3 right-3"
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
            >
              <AnimatedButton
                variant="glow"
                size="icon"
                loading={isLoading}
                icon={!isLoading && <Send size={16} />}
              />
            </motion.button>
          </div>

          {/* Loading States */}
          <AnimatePresence>
            {isLoading && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="space-y-4"
              >
                <RAGLoadingStates.QueryProcessing />
                <RAGLoadingStates.VectorSearch />
                <RAGLoadingStates.EmbeddingGeneration />
                <QuerySkeleton />
              </motion.div>
            )}
          </AnimatePresence>

          {/* Response */}
          <AnimatePresence>
            {showResponse && response && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-gradient-to-br from-green-50 to-blue-50 rounded-lg p-6 border border-green-200"
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold text-gray-800 flex items-center gap-2">
                    <Sparkles className="text-green-500" size={20} />
                    AI Response
                  </h3>
                  <div className="flex gap-2">
                    <AnimatedButton
                      variant="ghost"
                      size="sm"
                      icon={<Copy size={14} />}
                      onClick={() => {
                        navigator.clipboard.writeText(response);
                        toast({ title: "Copied!", description: "Response copied to clipboard" });
                      }}
                    />
                    <AnimatedButton
                      variant="ghost"
                      size="sm"
                      icon={<ThumbsUp size={14} />}
                      onClick={() => toast({ title: "Thanks!", description: "Feedback recorded" })}
                    />
                  </div>
                </div>
                <StreamingText 
                  text={response}
                  speed={30}
                  className="text-gray-700 leading-relaxed"
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );

  const renderSync = () => (
    <motion.div
      key="sync"
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <div className="bg-white rounded-xl shadow-lg p-6">
        <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
          <Zap className="text-purple-500" size={28} />
          Document Synchronization
        </h2>
        
        {uploadProgress > 0 && (
          <RAGLoadingStates.DocumentSync progress={uploadProgress} />
        )}
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
          <div className="space-y-4">
            <h3 className="font-semibold">Upload Progress</h3>
            <ProgressBar
              progress={uploadProgress}
              variant="gradient"
              color="purple"
              showLabel
              label="Document Processing"
            />
          </div>
          
          <div className="space-y-4">
            <h3 className="font-semibold">System Status</h3>
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Vector Database</span>
                <span className="text-green-600 font-medium">✓ Online</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">AI Models</span>
                <span className="text-green-600 font-medium">✓ Ready</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Document Index</span>
                <span className="text-blue-600 font-medium">↻ Updating</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );

  const renderShowcase = () => (
    <motion.div
      key="showcase"
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-8"
    >
      <div className="text-center">
        <h2 className="text-3xl font-bold bg-gradient-to-r from-orange-500 to-red-500 bg-clip-text text-transparent">
          Interactive Component Showcase
        </h2>
        <p className="text-gray-600 mt-2">Experience all the interactive elements in action</p>
      </div>

      {/* Button Variants */}
      <div className="bg-white rounded-xl shadow-lg p-6">
        <h3 className="text-xl font-bold mb-4">Animated Buttons</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <AnimatedButton variant="default" animation="bounce">Default</AnimatedButton>
          <AnimatedButton variant="glow" animation="slide">Glow</AnimatedButton>
          <AnimatedButton variant="premium" animation="wiggle">Premium</AnimatedButton>
          <AnimatedButton variant="outline" animation="pulse">Outline</AnimatedButton>
          <AnimatedButton variant="success" animation="rotate" badge="New">Success</AnimatedButton>
          <AnimatedButton variant="warning" animation="shake">Warning</AnimatedButton>
          <AnimatedButton variant="destructive" animation="bounce">Danger</AnimatedButton>
          <AnimatedButton variant="ghost" shimmer>Ghost</AnimatedButton>
        </div>
      </div>

      {/* Loading States */}
      <div className="bg-white rounded-xl shadow-lg p-6">
        <h3 className="text-xl font-bold mb-4">Loading States</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium mb-2">Processing States</h4>
            <div className="space-y-3">
              <RAGLoadingStates.QueryProcessing />
              <RAGLoadingStates.VectorSearch />
              <RAGLoadingStates.EmbeddingGeneration />
              <RAGLoadingStates.Success message="Task completed successfully!" />
            </div>
          </div>
          <div>
            <h4 className="font-medium mb-2">Progress Indicators</h4>
            <div className="space-y-4">
              <ProgressBar progress={75} variant="default" showLabel label="Default" />
              <ProgressBar progress={60} variant="gradient" color="green" showLabel label="Gradient" />
              <ProgressBar progress={45} variant="striped" color="orange" showLabel label="Striped" />
            </div>
          </div>
        </div>
      </div>

      {/* Typography Animations */}
      <div className="bg-white rounded-xl shadow-lg p-6">
        <h3 className="text-xl font-bold mb-4">Typography Animations</h3>
        <div className="space-y-4">
          <TypingAnimation 
            text="This text types itself out dynamically..."
            duration={3}
            className="text-lg text-blue-600"
          />
          <div className="flex items-center gap-4">
            <span>Loading</span>
            <LoadingDots />
          </div>
        </div>
      </div>
    </motion.div>
  );

  return (
    <>
      <MainLayout>
        {/* Header */}
        <motion.div 
          className="mb-8"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex items-center gap-4 mb-6">
            <motion.div
              className="w-16 h-16 bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 rounded-2xl flex items-center justify-center shadow-xl"
              animate={{ 
                rotate: [0, 5, -5, 0],
                scale: [1, 1.05, 1]
              }}
              transition={{ 
                duration: 4, 
                repeat: Infinity, 
                repeatDelay: 2 
              }}
            >
              <Sparkles className="text-white" size={32} />
            </motion.div>
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
                Interactive RAG Demo
              </h1>
              <motion.p 
                className="text-lg text-gray-500 mt-1"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
              >
                Tenant: <span className="font-semibold text-blue-600">{tenant || 'Demo Mode'}</span>
              </motion.p>
            </div>
          </div>
        </motion.div>

        {/* Navigation */}
        <motion.div 
          className="mb-8"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <AnimatedTabs
            tabs={tabs}
            activeTab={activeView}
            onTabChange={(tabId) => setActiveView(tabId as DemoView)}
            variant="pills"
            staggerDelay={0.05}
            className="justify-center"
          />
        </motion.div>

        {/* Content */}
        <AnimatedTabContent
          activeTab={activeView}
          animation="slide"
          direction="right"
          className="min-h-[600px]"
        >
          {activeView === 'dashboard' && renderDashboard()}
          {activeView === 'search' && renderSearch()}
          {activeView === 'sync' && renderSync()}
          {activeView === 'showcase' && renderShowcase()}
        </AnimatedTabContent>
      </MainLayout>

      {/* Floating Action Button */}
      <FloatingActionButton actions={floatingActions} />
      
      <Toaster />
    </>
  );
}

export default InteractiveDemo;