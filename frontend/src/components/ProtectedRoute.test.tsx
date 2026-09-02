import { render, screen } from '@testing-library/react';
import ProtectedRoute from './ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';

jest.mock('@/contexts/AuthContext', () => ({
  ...jest.requireActual('@/contexts/AuthContext'),
  useAuth: jest.fn(),
}));
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn() }) }));

const mockedUseAuth = useAuth as jest.Mock;

function setLocationHref() {
  const location = { href: '' };
  Object.defineProperty(window, 'location', { value: location, writable: true });
  return location;
}

describe('ProtectedRoute', () => {
  it('redirects to /login when there is no user', () => {
    const location = setLocationHref();
    mockedUseAuth.mockReturnValue({ user: null, loading: false });

    render(<ProtectedRoute><div>secret</div></ProtectedRoute>);

    expect(location.href).toBe('/login');
    expect(screen.queryByText('secret')).not.toBeInTheDocument();
  });

  it('redirects to / when the user role is not allowed', () => {
    const location = setLocationHref();
    mockedUseAuth.mockReturnValue({
      user: { id: 1, name: 'A', email: 'a@b.com', role: 'Wildlife Researcher' },
      loading: false,
    });

    render(
      <ProtectedRoute allowedRoles={['Administrator']}>
        <div>secret</div>
      </ProtectedRoute>
    );

    expect(location.href).toBe('/');
    expect(screen.queryByText('secret')).not.toBeInTheDocument();
  });

  it('renders children when the role is allowed', () => {
    setLocationHref();
    mockedUseAuth.mockReturnValue({
      user: { id: 1, name: 'A', email: 'a@b.com', role: 'Administrator' },
      loading: false,
    });

    render(
      <ProtectedRoute allowedRoles={['Administrator']}>
        <div>secret</div>
      </ProtectedRoute>
    );

    expect(screen.getByText('secret')).toBeInTheDocument();
  });
});
