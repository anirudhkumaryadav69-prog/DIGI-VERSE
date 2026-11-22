import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import AppErrorBoundary from './components/common/AppErrorBoundary';
import AppRoutes from './routes/AppRoutes';

const App = () => {
  return (
    <AppErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </AppErrorBoundary>
  );
};

export default App;
