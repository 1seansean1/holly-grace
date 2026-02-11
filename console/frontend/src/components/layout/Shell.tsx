import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { HollyProvider } from '@/lib/HollyContext';
import HollySidebar from '@/components/holly/HollySidebar';

export default function Shell() {
  return (
    <HollyProvider>
      <div className="flex h-full overflow-hidden">
        <Sidebar />
        <main className="flex-1 flex flex-col overflow-hidden min-w-0">
          <Outlet />
        </main>
        <HollySidebar />
      </div>
    </HollyProvider>
  );
}
