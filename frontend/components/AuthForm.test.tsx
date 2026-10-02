import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthForm } from './AuthForm';

const authActions = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
  replace: vi.fn(),
}));

vi.mock('./AuthProvider', () => ({ useAuth: () => authActions }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace: authActions.replace }) }));

describe('AuthForm', () => {
  beforeEach(() => {
    authActions.login.mockReset().mockResolvedValue(undefined);
    authActions.register.mockReset().mockResolvedValue(undefined);
    authActions.replace.mockReset();
  });

  it('registers a student without allowing public role selection', async () => {
    render(<AuthForm mode="register" />);
    fireEvent.change(screen.getByRole('textbox', { name: 'Email' }), {
      target: { value: 'learner@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'Long-password-123!' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    await waitFor(() => expect(authActions.register).toHaveBeenCalledWith(
      'learner@example.com',
      'Long-password-123!',
    ));
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(authActions.replace).toHaveBeenCalledWith('/');
  });
});