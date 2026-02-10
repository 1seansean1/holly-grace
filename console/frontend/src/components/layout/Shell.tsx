import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

export default function Shell() {
  return (
    <div className="flex h-full overflow-hidden">
      <Sidebar />
      <main className="flex-1 flex flex-col overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
