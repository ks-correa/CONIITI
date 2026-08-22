import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import Profile from '../../pages/Profile';
import { getOwnProfile, updateOwnProfile } from '../../services/userService';


const refreshUser = vi.fn();

vi.mock('../../context/AuthContext', () => ({
    useAuth: () => ({ refreshUser }),
}));

vi.mock('../../services/userService', () => ({
    getOwnProfile: vi.fn(),
    updateOwnProfile: vi.fn(),
}));


describe('Perfil de usuario', () => {
    afterEach(() => vi.clearAllMocks());

    it('permite completar datos opcionales después de OAuth', async () => {
        getOwnProfile.mockResolvedValue({
            id: 'u1', email: 'oauth@example.com', full_name: 'OAuth User', role: 'external',
            first_name: null, last_name: null, institution: null, career: null,
            gender: null, document: null, institutional_code: null, profile_completed: false,
        });
        updateOwnProfile.mockImplementation(async (payload) => ({
            id: 'u1', email: 'oauth@example.com', role: 'external', full_name: `${payload.first_name} ${payload.last_name}`,
            ...payload, profile_completed: true,
        }));

        render(<Profile />);
        await screen.findByDisplayValue('oauth@example.com');

        fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'Ana' } });
        fireEvent.change(screen.getByLabelText('Apellido'), { target: { value: 'Ríos' } });
        fireEvent.change(screen.getByLabelText('Carrera o programa'), { target: { value: 'Sistemas' } });
        fireEvent.click(screen.getByRole('button', { name: 'Guardar perfil' }));

        await waitFor(() => expect(updateOwnProfile).toHaveBeenCalledWith(expect.objectContaining({
            first_name: 'Ana', last_name: 'Ríos', career: 'Sistemas',
        })));
        expect(refreshUser).toHaveBeenCalledTimes(1);
        expect(await screen.findByText('Tu perfil se actualizo correctamente.')).toBeInTheDocument();
    });
});
