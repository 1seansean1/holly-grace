import { BrowserRouter, Routes, Route } from 'react-router-dom';
import ErrorBoundary from '@/components/ErrorBoundary';
import { AuthProvider, AuthGuard } from '@/lib/auth';
import Shell from '@/components/layout/Shell';
import LoginPage from '@/pages/LoginPage';
import WorkflowPage from '@/pages/WorkflowPage';
import WorkflowsPage from '@/pages/WorkflowsPage';
import LogsPage from '@/pages/LogsPage';
import TracesPage from '@/pages/TracesPage';
import CostsPage from '@/pages/CostsPage';
import AgentsPage from '@/pages/AgentsPage';
import ToolsPage from '@/pages/ToolsPage';
import McpPage from '@/pages/McpPage';
import HealthPage from '@/pages/HealthPage';
import ApprovalsPage from '@/pages/ApprovalsPage';
import EvalPage from '@/pages/EvalPage';
import MorphPage from '@/pages/MorphPage';
import SystemPage from '@/pages/SystemPage';
import ChatPage from '@/pages/ChatPage';
import TowerPage from '@/pages/TowerPage';
import HierarchyPage from '@/pages/HierarchyPage';
import AutonomyPage from '@/pages/AutonomyPage';
import IMDesignerPage from '@/pages/IMDesignerPage';
export default function App() {
  return (
    <ErrorBoundary>
    <BrowserRouter>
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<AuthGuard><Shell /></AuthGuard>}>
          <Route index element={<TowerPage />} />
          <Route path="canvas" element={<WorkflowPage />} />
          <Route path="workflows" element={<WorkflowsPage />} />
          <Route path="agents" element={<AgentsPage />} />
          <Route path="tower" element={<TowerPage />} />
          <Route path="hierarchy" element={<HierarchyPage />} />
          <Route path="im-designer" element={<IMDesignerPage />} />
          <Route path="approvals" element={<ApprovalsPage />} />
          <Route path="eval" element={<EvalPage />} />
          <Route path="morph" element={<MorphPage />} />
          <Route path="logs" element={<LogsPage />} />
          <Route path="traces" element={<TracesPage />} />
          <Route path="costs" element={<CostsPage />} />
          <Route path="tools" element={<ToolsPage />} />
          <Route path="mcp" element={<McpPage />} />
          <Route path="health" element={<HealthPage />} />
          <Route path="autonomy" element={<AutonomyPage />} />
          <Route path="system" element={<SystemPage />} />
          <Route path="chat" element={<ChatPage />} />
        </Route>
      </Routes>
    </AuthProvider>
    </BrowserRouter>
    </ErrorBoundary>
  );
}
