const requestUse = jest.fn();
const responseUse = jest.fn();
const mockAxiosPost = jest.fn();
// A real axios instance is a callable function with properties attached --
// mirror that shape so `api(originalRequest)` (the retry call) works.
const mockInstance = Object.assign(jest.fn(), {
  interceptors: { request: { use: requestUse }, response: { use: responseUse } },
});

jest.mock('axios', () => ({
  __esModule: true,
  default: {
    create: jest.fn(() => mockInstance),
    post: (...args: unknown[]) => mockAxiosPost(...args),
  },
}));

describe('api response interceptor', () => {
  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
  });

  it('refreshes the access token and retries once on a 401', async () => {
    mockAxiosPost.mockResolvedValue({ data: { access_token: 'new-token' } });
    mockInstance.mockResolvedValue({ data: 'ok' });

    // Re-import so the module wires its interceptors against the fresh mocks.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    require('./api');
    const onRejected = responseUse.mock.calls[0][1];

    const originalRequest: { _retry?: boolean; headers: Record<string, string> } = { headers: {} };
    const result = await onRejected({ response: { status: 401 }, config: originalRequest });

    expect(mockAxiosPost).toHaveBeenCalledWith(
      expect.stringContaining('/auth/refresh'),
      {},
      { withCredentials: true }
    );
    expect(originalRequest.headers.Authorization).toBe('Bearer new-token');
    expect(originalRequest._retry).toBe(true);
    expect(result).toEqual({ data: 'ok' });
  });

  it('does not retry a second time for the same request', async () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    require('./api');
    const onRejected = responseUse.mock.calls[0][1];

    const originalRequest = { _retry: true, headers: {} };
    await expect(
      onRejected({ response: { status: 401 }, config: originalRequest })
    ).rejects.toBeDefined();
    expect(mockAxiosPost).not.toHaveBeenCalled();
  });
});
