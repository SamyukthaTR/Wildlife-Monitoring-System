import { render, screen, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from './AuthContext';
import api, { setAccessToken } from '@/lib/api';

jest.mock('@/lib/api', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn() },
  setAccessToken: jest.fn(),
}));

const mockedApi = api as jest.Mocked<typeof api>;

function Probe() {
  const { user, loading, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="user">{user ? user.email : 'none'}</span>
      <button onClick={() => login('token-123')}>login</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

describe('AuthProvider', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (mockedApi.post as jest.Mock).mockRejectedValue(new Error('no refresh token'));
  });

  it('starts unauthenticated when the silent refresh fails', async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'));
    expect(screen.getByTestId('user').textContent).toBe('none');
  });

  it('login() sets the access token and loads the user', async () => {
    (mockedApi.get as jest.Mock).mockResolvedValue({
      data: { id: 1, name: 'Jane', email: 'jane@example.com', role: 'Wildlife Researcher' },
    });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'));

    screen.getByText('login').click();

    await waitFor(() => expect(screen.getByTestId('user').textContent).toBe('jane@example.com'));
    expect(setAccessToken).toHaveBeenCalledWith('token-123');
  });

  it('logout() clears the user and access token', async () => {
    (mockedApi.get as jest.Mock).mockResolvedValue({
      data: { id: 1, name: 'Jane', email: 'jane@example.com', role: 'Wildlife Researcher' },
    });
    (mockedApi.post as jest.Mock).mockResolvedValue({ data: {} });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    screen.getByText('login').click();
    await waitFor(() => expect(screen.getByTestId('user').textContent).toBe('jane@example.com'));

    screen.getByText('logout').click();
    await waitFor(() => expect(screen.getByTestId('user').textContent).toBe('none'));
    expect(setAccessToken).toHaveBeenCalledWith(null);
  });
});
