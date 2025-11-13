import { Navigate, Route, Routes } from 'react-router-dom';

import ProtectedLayout from './components/ProtectedLayout';
import FirstVisitPage from './pages/FirstVisitPage';
import AdminDiagnosisCodesPage from './pages/AdminDiagnosisCodesPage';
import LoginPage from './pages/LoginPage';
import PatientCreatePage from './pages/PatientCreatePage';
import PatientDetailPage from './pages/PatientDetailPage';
import PatientsPage from './pages/PatientsPage';
import StartPage from './pages/StartPage';

const App = () => {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedLayout />}>
          <Route index element={<Navigate to="/start" replace />} />
          <Route path="/start" element={<StartPage />} />
          <Route path="/patients" element={<PatientsPage />} />
          <Route path="/patients/new" element={<PatientCreatePage />} />
          <Route path="/patients/:patientId" element={<PatientDetailPage />} />
          <Route path="/first-visit" element={<FirstVisitPage />} />
          <Route path="/admin/diagnosis-codes" element={<AdminDiagnosisCodesPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/start" replace />} />
      </Routes>
    </div>
  );
};

export default App;
