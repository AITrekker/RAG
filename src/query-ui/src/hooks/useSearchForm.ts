import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const searchFormSchema = z.object({
  query: z
    .string()
    .min(2, 'Search query must be at least 2 characters')
    .max(200, 'Search query cannot exceed 200 characters'),
  filters: z.object({
    dateRange: z.object({
      start: z.string().optional(),
      end: z.string().optional(),
    }),
    fileTypes: z.array(z.string()).optional(),
    sources: z.array(z.string()).optional(),
  }).optional(),
});

export type SearchFormData = z.infer<typeof searchFormSchema>;

export function useSearchForm() {
  const form = useForm<SearchFormData>({
    resolver: zodResolver(searchFormSchema),
    defaultValues: {
      query: '',
      filters: {
        dateRange: {},
        fileTypes: [],
        sources: [],
      },
    },
  });

  const { formState: { errors }, handleSubmit } = form;

  const onSubmit = handleSubmit((data) => {
    // Form is valid, handle submission
    console.log('Form submitted:', data);
  });

  return {
    form,
    errors,
    onSubmit,
  };
} 