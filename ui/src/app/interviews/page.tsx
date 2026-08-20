'use client';

import { CheckCircle2, ChevronDown, ClipboardList, Loader2, RefreshCw, XCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { listInterviewsApiV1InterviewsGet } from '@/client/sdk.gen';
import type { InterviewResult, InterviewsResponse } from '@/client/types.gen';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useAuth } from '@/lib/auth';
import { cn } from '@/lib/utils';

const VERDICT_COLORS: Record<string, string> = {
  pass: '#10b981', // emerald-500
  review: '#f59e0b', // amber-500
  fail: '#ef4444', // red-500
};

function verdictBadgeVariant(verdict?: string | null): 'success' | 'secondary' | 'destructive' | 'default' {
  switch ((verdict || '').toLowerCase()) {
    case 'pass':
      return 'success';
    case 'review':
      return 'secondary';
    case 'fail':
      return 'destructive';
    default:
      return 'default';
  }
}

function SummaryCard({
  title,
  value,
  sub,
  icon,
}: {
  title: string;
  value: string | number;
  sub?: string;
  icon?: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}

interface InterviewDetailProps {
  interview: InterviewResult;
}

function InterviewDetail({ interview }: InterviewDetailProps) {
  const dimensions = interview.dimensions;
  const dimensionEntries = dimensions && typeof dimensions === 'object'
    ? Object.entries(dimensions as Record<string, unknown>)
    : [];

  const strengths = Array.isArray(interview.strengths) ? interview.strengths : [];
  const improvements = Array.isArray(interview.improvements) ? interview.improvements : [];

  return (
    <div className="space-y-4">
      {dimensionEntries.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-semibold">Dimension Scores</h4>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {dimensionEntries.map(([name, value]) => {
              const dim = (value && typeof value === 'object' ? value : {}) as {
                score?: number;
                evidence?: string;
              };
              return (
                <div key={name} className="rounded-md border border-border/60 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium capitalize">
                      {name.replace(/_/g, ' ')}
                    </span>
                    <Badge variant={dim.score != null && dim.score >= 4 ? 'success' : 'secondary'}>
                      {dim.score ?? '—'}
                    </Badge>
                  </div>
                  {dim.evidence && (
                    <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                      &ldquo;{dim.evidence}&rdquo;
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {strengths.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-semibold">Strengths</h4>
          <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
            {strengths.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {improvements.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-semibold">Improvements</h4>
          <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
            {improvements.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {interview.transcript && (
        <div>
          <h4 className="mb-2 text-sm font-semibold">Transcript</h4>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md border border-border/60 bg-muted/40 p-3 text-xs text-muted-foreground">
            {interview.transcript}
          </pre>
        </div>
      )}

      {dimensionEntries.length === 0 && strengths.length === 0 && improvements.length === 0 && !interview.transcript && (
        <p className="text-sm text-muted-foreground">No detailed results for this interview.</p>
      )}
    </div>
  );
}

export default function InterviewsPage() {
  const auth = useAuth();
  const [data, setData] = useState<InterviewsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const fetchInterviews = async () => {
    if (!auth.isAuthenticated) return;
    setLoading(true);
    setError(null);
    try {
      const response = await listInterviewsApiV1InterviewsGet();
      if (response.data) {
        setData(response.data);
      }
    } catch (err) {
      console.error('Failed to fetch interviews:', err);
      setError('Failed to load interview results');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInterviews();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.isAuthenticated]);

  const chartData = useMemo(() => {
    if (!data) return [];
    return [
      { verdict: 'Pass', count: data.summary.pass_count, fill: VERDICT_COLORS.pass },
      { verdict: 'Review', count: data.summary.review_count, fill: VERDICT_COLORS.review },
      { verdict: 'Fail', count: data.summary.fail_count, fill: VERDICT_COLORS.fail },
    ].filter((d) => d.count > 0);
  }, [data]);

  const toggleExpanded = (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (!auth.isAuthenticated) {
    return null;
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold">Interviews</h1>
          <p className="text-sm text-muted-foreground">
            Graded interview results from the mock-interview voice agent
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchInterviews} disabled={loading}>
          <RefreshCw className={cn('mr-2 h-4 w-4', loading && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {loading && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-[110px]" />
            ))}
          </div>
          <Skeleton className="h-[300px]" />
        </div>
      )}

      {error && !loading && (
        <Card className="p-6">
          <p className="text-center text-red-500">{error}</p>
        </Card>
      )}

      {!loading && !error && data && !data.configured && (
        <Card className="p-6">
          <div className="flex items-start gap-3">
            <ClipboardList className="mt-0.5 h-5 w-5 text-muted-foreground" />
            <div>
              <p className="font-semibold">Interview grading is not configured</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Set <code className="rounded bg-muted px-1 py-0.5">GRIST_DOC_ID</code> and{' '}
                <code className="rounded bg-muted px-1 py-0.5">GRIST_API_KEY</code> in your
                environment and restart the API to surface graded interviews here.
              </p>
            </div>
          </div>
        </Card>
      )}

      {!loading && !error && data && data.configured && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <SummaryCard
              title="Total Interviews"
              value={data.summary.total.toLocaleString()}
              sub="Graded results"
              icon={<ClipboardList className="h-4 w-4 text-muted-foreground" />}
            />
            <SummaryCard
              title="Passed"
              value={data.summary.pass_count.toLocaleString()}
              sub="Score ≥ 75"
              icon={<CheckCircle2 className="h-4 w-4 text-green-500" />}
            />
            <SummaryCard
              title="Needs Review"
              value={data.summary.review_count.toLocaleString()}
              sub="Score 60–74"
              icon={<Loader2 className="h-4 w-4 text-amber-500" />}
            />
            <SummaryCard
              title="Failed"
              value={data.summary.fail_count.toLocaleString()}
              sub={data.summary.average_score != null
                ? `Avg score: ${data.summary.average_score}`
                : 'Score < 60'}
              icon={<XCircle className="h-4 w-4 text-red-500" />}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle>Verdict Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                {chartData.length === 0 ? (
                  <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                    No graded interviews yet
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
                      <XAxis type="number" tick={{ fontSize: 12 }} allowDecimals={false} />
                      <YAxis type="category" dataKey="verdict" tick={{ fontSize: 12 }} width={70} />
                      <Tooltip
                        cursor={{ fill: 'rgba(0,0,0,0.05)' }}
                        content={({ active, payload }) => {
                          if (active && payload && payload[0]) {
                            const d = payload[0].payload as { verdict: string; count: number };
                            return (
                              <div className="bg-background border rounded-lg shadow-lg p-3">
                                <p className="font-semibold">{d.verdict}</p>
                                <p className="text-sm">Count: {d.count}</p>
                              </div>
                            );
                          }
                          return null;
                        }}
                      />
                      <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={32}>
                        {chartData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.fill} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Results</CardTitle>
              </CardHeader>
              <CardContent>
                {data.interviews.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">
                    No interviews have been graded yet. Run the interview smoke test to see results here.
                  </p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-8" />
                        <TableHead>Student</TableHead>
                        <TableHead>Phone</TableHead>
                        <TableHead>Run</TableHead>
                        <TableHead className="text-right">Score</TableHead>
                        <TableHead>Verdict</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.interviews.map((interview) => {
                        const isOpen = expanded.has(interview.id);
                        return (
                          <TableRow
                            key={interview.id}
                            className={cn('cursor-pointer', isOpen && 'bg-muted/40')}
                            onClick={() => toggleExpanded(interview.id)}
                          >
                            <TableCell>
                              <ChevronDown className={cn('h-4 w-4 transition-transform', isOpen && 'rotate-180')} />
                            </TableCell>
                            <TableCell className="font-medium">
                              {interview.student || '—'}
                            </TableCell>
                            <TableCell className="text-muted-foreground">
                              {interview.phone || '—'}
                            </TableCell>
                            <TableCell className="text-muted-foreground">
                              {interview.run_id || '—'}
                            </TableCell>
                            <TableCell className="text-right font-semibold">
                              {interview.score != null ? interview.score : '—'}
                            </TableCell>
                            <TableCell>
                              <Badge variant={verdictBadgeVariant(interview.verdict)}>
                                {interview.verdict || '—'}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                )}

                {data.interviews.map((interview) => {
                  if (!expanded.has(interview.id)) return null;
                  return (
                    <div key={`detail-${interview.id}`} className="border-t border-border/60 p-4">
                      <InterviewDetail interview={interview} />
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
