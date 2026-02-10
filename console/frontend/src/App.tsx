import { BrowserRouter, Routes, Route } from 'react-router-dom';
import ErrorBoundary from '@/components/ErrorBoundary';
import Shell from '@/components/layout/Shell';
import WorkflowPage from '@/pages/WorkflowPage';
import WorkflowsPage from '@/pages/WorkflowsPage';
import LogsPage from '@/pages/LogsPage';
import TracesPage from '@/pages/TracesPage';
import CostsPage from '@/pages/CostsPage';
import AgentsPage from '@/pages/AgentsPage';
import ToolsPage from '@/pages/ToolsPage';
import HealthPage from '@/pages/HealthPage';
import ApprovalsPage from '@/pages/ApprovalsPage';
import EvalPage from '@/pages/EvalPage';
import MorphPage from '@/pages/MorphPage';
import SystemPage from '@/pages/SystemPage';

export default function App() {
  return (
    <ErrorBoundary>
    <BrowserRouter>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<WorkflowPage />} />
          <Route path="workflows" element={<WorkflowsPage />} />
          <Route path="agents" element={<AgentsPage />} />
          <Route path="approvals" element={<ApprovalsPage />} />
          <Route path="eval" element={<EvalPage />} />
          <Route path="morph" element={<MorphPage />} />
          <Route path="logs" element={<LogsPage />} />
          <Route path="traces" element={<TracesPage />} />
          <Route path="costs" element={<CostsPage />} />
          <Route path="tools" element={<ToolsPage />} />
          <Route path="health" element={<HealthPage />} />
          <Route path="system" element={<SystemPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
    </ErrorBoundary>
  );
}
