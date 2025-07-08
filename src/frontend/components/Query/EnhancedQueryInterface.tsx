import { useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useMutation } from "@tanstack/react-query";
import { 
  Send, 
  Sparkles, 
  FileText, 
  Clock, 
  TrendingUp, 
  Copy, 
  ThumbsUp, 
  ThumbsDown,
  RotateCcw,
  Zap
} from "lucide-react";

import { QueryService } from "@/src/services/api.generated";
import type {
  ApiError,
  QueryRequest,
  QueryResponse,
  SourceCitation,
} from "@/src/services/api.generated";

import { useToast } from "@/components/ui/use-toast";
import { AnimatedButton } from "@/components/ui/animated-button";
import { TypingAnimation, StreamingText, LoadingDots } from "@/components/ui/typing-animation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useTenant } from "@/contexts/TenantContext";
import { cn } from "@/lib/utils";

interface QueryHistoryItem {
  id: string;
  query: string;
  timestamp: Date;
  confidence: number;
}

export const EnhancedQueryInterface = () => {
  const { tenant } = useTenant();
  const { toast } = useToast();
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [queryHistory, setQueryHistory] = useState<QueryHistoryItem[]>([]);
  const [streamingResponse, setStreamingResponse] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const suggestions = [
    "What are our company policies?",
    "How do I request time off?", 
    "What are the safety protocols?",
    "Where can I find the employee handbook?",
    "What benefits are available?"
  ];

  const mutation = useMutation<QueryResponse, ApiError, QueryRequest>({
    mutationFn: (requestBody) => {
      setIsLoading(true);
      setStreamingResponse("");
      return QueryService.processQueryApiV1QueryPost(requestBody);
    },
    onSuccess: (data) => {
      setResponse(data);
      setIsLoading(false);
      
      // Add to history
      setQueryHistory(prev => [{
        id: Date.now().toString(),
        query,
        timestamp: new Date(),
        confidence: data.confidence || 0
      }, ...prev.slice(0, 4)]); // Keep last 5 queries
      
      // Simulate streaming response
      if (data.answer) {
        setStreamingResponse(data.answer);
      }
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: `An error occurred: ${error.body?.detail || error.message}`,
        variant: "destructive",
      });
      setIsLoading(false);
    },
  });

  const handleQuery = () => {
    if (query.trim() && tenant) {
      mutation.mutate({ query, tenant_id: tenant });
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleQuery();
    }
  };
  
  const handleQueryChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setQuery(event.target.value);
    setShowSuggestions(event.target.value.length > 0);
  };

  const useSuggestion = (suggestion: string) => {
    setQuery(suggestion);
    setShowSuggestions(false);
    textareaRef.current?.focus();
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: "Copied!",
      description: "Response copied to clipboard",
    });
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return "text-green-600 bg-green-100";
    if (confidence >= 0.6) return "text-yellow-600 bg-yellow-100";
    return "text-red-600 bg-red-100";
  };

  return (
    <div className="space-y-6">
      {/* Quick Stats */}
      <motion.div 
        className="grid grid-cols-1 md:grid-cols-3 gap-4"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="bg-gradient-to-r from-blue-500 to-blue-600 text-white p-4 rounded-lg">
          <div className="flex items-center gap-2">
            <Zap size={20} />
            <span className="text-sm font-medium">Recent Queries</span>
          </div>
          <div className="text-2xl font-bold mt-1">{queryHistory.length}</div>
        </div>
        
        <div className="bg-gradient-to-r from-green-500 to-green-600 text-white p-4 rounded-lg">
          <div className="flex items-center gap-2">
            <TrendingUp size={20} />
            <span className="text-sm font-medium">Avg Confidence</span>
          </div>
          <div className="text-2xl font-bold mt-1">
            {queryHistory.length > 0 
              ? Math.round(queryHistory.reduce((acc, item) => acc + item.confidence, 0) / queryHistory.length * 100)
              : 0}%
          </div>
        </div>
        
        <div className="bg-gradient-to-r from-purple-500 to-purple-600 text-white p-4 rounded-lg">
          <div className="flex items-center gap-2">
            <FileText size={20} />
            <span className="text-sm font-medium">Documents</span>
          </div>
          <div className="text-2xl font-bold mt-1">156</div>
        </div>
      </motion.div>

      {/* Query Interface */}
      <Card className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-50 to-indigo-50 opacity-30" />
        
        <CardHeader className="relative">
          <div className="flex items-center gap-2">
            <Sparkles className="text-blue-500" size={24} />
            <CardTitle className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              Ask Your Question
            </CardTitle>
          </div>
          <CardDescription>
            <TypingAnimation 
              text={`Ask questions about your documents for tenant: ${tenant || 'None'}`}
              duration={2}
              className="text-sm"
            />
          </CardDescription>
        </CardHeader>
        
        <CardContent className="relative space-y-4">
          <div className="relative">
            <Textarea
              ref={textareaRef}
              value={query}
              onChange={handleQueryChange}
              onKeyDown={handleKeyDown}
              onFocus={() => setShowSuggestions(query.length > 0)}
              placeholder="Type your question here..."
              className="min-h-[120px] pr-12 resize-none border-2 focus:border-blue-500 transition-all duration-200"
              disabled={!tenant}
            />
            
            {/* Send button */}
            <motion.div 
              className="absolute bottom-3 right-3"
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
            >
              <AnimatedButton
                onClick={handleQuery}
                disabled={isLoading || !tenant || !query.trim()}
                size="icon"
                variant="glow"
                animation="bounce"
                loading={isLoading}
                icon={!isLoading && <Send size={16} />}
              />
            </motion.div>

            {/* Suggestions dropdown */}
            <AnimatePresence>
              {showSuggestions && (
                <motion.div
                  className="absolute top-full left-0 right-0 bg-white border border-gray-200 rounded-lg shadow-lg z-10 mt-1"
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                >
                  <div className="p-2 space-y-1">
                    <div className="text-xs font-medium text-gray-500 px-2 py-1">Suggestions:</div>
                    {suggestions.map((suggestion, index) => (
                      <motion.button
                        key={suggestion}
                        onClick={() => useSuggestion(suggestion)}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 rounded-md transition-colors"
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.05 }}
                        whileHover={{ x: 4 }}
                      >
                        {suggestion}
                      </motion.button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Loading State */}
          <AnimatePresence>
            {isLoading && (
              <motion.div
                className="flex items-center justify-center py-8"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <div className="text-center space-y-4">
                  <LoadingDots className="justify-center" />
                  <TypingAnimation 
                    text="Analyzing your query and searching documents..."
                    duration={3}
                    className="text-sm text-gray-600"
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </CardContent>
      </Card>

      {/* Response */}
      <AnimatePresence>
        {response && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="space-y-4"
          >
            <Card className="border-l-4 border-l-blue-500">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <Sparkles className="text-blue-500" size={20} />
                    Answer
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge className={cn("font-medium", getConfidenceColor(response.confidence))}>
                      {Math.round(response.confidence * 100)}% confident
                    </Badge>
                    <AnimatedButton
                      variant="ghost"
                      size="icon"
                      onClick={() => copyToClipboard(response.answer)}
                      icon={<Copy size={16} />}
                    />
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <StreamingText 
                  text={response.answer}
                  speed={30}
                  className="text-gray-800 leading-relaxed whitespace-pre-wrap"
                />
                
                {/* Action buttons */}
                <div className="flex items-center gap-2 mt-4 pt-4 border-t">
                  <AnimatedButton
                    variant="ghost"
                    size="sm"
                    icon={<ThumbsUp size={16} />}
                    animation="bounce"
                  >
                    Helpful
                  </AnimatedButton>
                  <AnimatedButton
                    variant="ghost"
                    size="sm"
                    icon={<ThumbsDown size={16} />}
                    animation="bounce"
                  >
                    Not helpful
                  </AnimatedButton>
                  <AnimatedButton
                    variant="ghost"
                    size="sm"
                    icon={<RotateCcw size={16} />}
                    animation="bounce"
                  >
                    Regenerate
                  </AnimatedButton>
                </div>
              </CardContent>
            </Card>

            {/* Sources */}
            {response.sources && response.sources.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="text-green-500" size={20} />
                    Sources ({response.sources.length})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {response.sources.map((citation: SourceCitation, index: number) => (
                      <motion.div
                        key={index}
                        className="p-4 bg-gray-50 rounded-lg border-l-4 border-l-green-500"
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.1 }}
                        whileHover={{ scale: 1.02 }}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-semibold text-green-700">
                            {citation.filename}
                          </span>
                          <Badge variant="outline">
                            Page {citation.page_number}
                          </Badge>
                        </div>
                        <p className="text-sm text-gray-600 italic">
                          "{citation.text}"
                        </p>
                      </motion.div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Query History */}
      {queryHistory.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="text-purple-500" size={20} />
              Recent Queries
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {queryHistory.map((item, index) => (
                <motion.button
                  key={item.id}
                  onClick={() => setQuery(item.query)}
                  className="w-full text-left p-3 bg-gray-50 hover:bg-blue-50 rounded-lg transition-colors group"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  whileHover={{ x: 4 }}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-800 group-hover:text-blue-800 truncate">
                      {item.query}
                    </span>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <Badge className={cn("text-xs", getConfidenceColor(item.confidence))}>
                        {Math.round(item.confidence * 100)}%
                      </Badge>
                      <span className="text-xs text-gray-500">
                        {item.timestamp.toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                </motion.button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};