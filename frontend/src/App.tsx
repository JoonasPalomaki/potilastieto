import { Navigate, Route, Routes } from 'react-router-dom';

import ProtectedLayout from './components/ProtectedLayout';
import LoginPage from './pages/LoginPage';
import PatientsPage from './pages/PatientsPage';

const App = () => {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedLayout />}>
          <Route index element={<Navigate to="/patients" replace />} />
          <Route path="/patients" element={<PatientsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/patients" replace />} />
      </Routes>
    </div>
  );
};

export default App;
