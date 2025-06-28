import { useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";
import { useMutation } from "@tanstack/react-query";

import { QueryService } from "@/src/services/api.generated";
import type {
  ApiError,
  QueryRequest,
  QueryResponse,
  SourceCitation,
} from "@/src/services/api.generated";

import { useToast } from "@/components/ui/use-toast";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useTenant } from "@/contexts/TenantContext";

export const QueryInterface = () => {
  const { tenant } = useTenant();
  const { toast } = useToast();
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const mutation = useMutation<QueryResponse, ApiError, QueryRequest>({
    mutationFn: (requestBody) => {
      setIsLoading(true);
      return QueryService.processQueryApiV1QueryPost(requestBody);
    },
    onSuccess: (data) => {
      setResponse(data);
      setIsLoading(false);
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
  }

  return (
    <div className="flex flex-col h-full">
      <Card className="flex-grow">
        <CardHeader>
          <CardTitle>Query</CardTitle>
          <CardDescription>
            Ask a question to the documents for tenant:{" "}
            <span className="font-bold text-primary">{tenant}</span>
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex-grow flex flex-col gap-4">
            <Textarea
              ref={textareaRef}
              value={query}
              onChange={handleQueryChange}
              onKeyDown={handleKeyDown}
              placeholder="Type your question here..."
              className="flex-grow"
              rows={5}
              disabled={!tenant}
            />
            <Button onClick={handleQuery} disabled={isLoading || !tenant}>
              {isLoading ? "Thinking..." : "Send Query"}
            </Button>
          </div>
        </CardContent>
      </Card>
      {response && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Answer</CardTitle>
            <CardDescription>
              Confidence: {(response.confidence * 100).toFixed(0)}%
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap">{response.answer}</p>
            {response.sources && response.sources.length > 0 && (
              <div className="mt-4">
                <h4 className="font-bold">Sources:</h4>
                <ul className="list-disc pl-5 space-y-2 mt-2">
                  {response.sources.map(
                    (citation: SourceCitation, index: number) => (
                      <li key={index} className="text-sm">
                        <span className="font-semibold">
                          {citation.filename}:
                        </span>{" "}
                        Page {citation.page_number}
                        <p className="pl-2 italic text-gray-500">
                          "{citation.text}"
                        </p>
                      </li>
                    )
                  )}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};