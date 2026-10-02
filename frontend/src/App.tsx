import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout.tsx'
import DashboardPage from './pages/DashboardPage.tsx'
import ImportPage from './pages/ImportPage.tsx'
import InstallmentsPage from './pages/InstallmentsPage.tsx'
import RecurrencesPage from './pages/RecurrencesPage.tsx'
import ReviewPage from './pages/ReviewPage.tsx'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="importar" element={<ImportPage />} />
        <Route path="revisar" element={<ReviewPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="recorrentes" element={<RecurrencesPage />} />
        <Route path="parcelas" element={<InstallmentsPage />} />
      </Route>
    </Routes>
  )
}
