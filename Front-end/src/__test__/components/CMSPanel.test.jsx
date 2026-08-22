import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import CMSPanel from '../../components/CMSPanel';
import {
    fetchAdminContentSection,
    updateContentCard,
} from '../../services/contentService';


vi.mock('../../components/admin/AssetPicker', () => ({
    default: () => <div>Selector de recursos</div>,
}));

vi.mock('../../services/contentService', () => ({
    createContentCard: vi.fn(),
    deleteContentCard: vi.fn(),
    fetchAdminContentSection: vi.fn(),
    updateContentCard: vi.fn(),
}));


describe('CMSPanel', () => {
    afterEach(() => vi.clearAllMocks());

    it('no reenvía metadatos de solo lectura al editar una tarjeta', async () => {
        const existing = {
            id: 'card-1',
            section: 'memorias',
            title: 'Memoria original',
            subtitle: null,
            year: 2025,
            description: 'Descripción',
            image_url: null,
            link_url: null,
            asset_id: null,
            media_type: 'document',
            is_active: true,
            sort_order: 2,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-02T00:00:00Z',
        };
        fetchAdminContentSection.mockResolvedValue([existing]);
        updateContentCard.mockResolvedValue({ ...existing, title: 'Memoria actualizada' });

        render(<CMSPanel />);
        await screen.findByText('Memoria original');
        fireEvent.click(screen.getByTitle('Editar'));
        fireEvent.change(screen.getByLabelText('Título'), { target: { value: 'Memoria actualizada' } });
        fireEvent.click(screen.getByRole('button', { name: /guardar/i }));

        await waitFor(() => expect(updateContentCard).toHaveBeenCalledTimes(1));
        const [cardId, payload] = updateContentCard.mock.calls[0];
        expect(cardId).toBe('card-1');
        expect(payload).toEqual(expect.objectContaining({
            section: 'memorias',
            title: 'Memoria actualizada',
            media_type: 'document',
            sort_order: 2,
        }));
        expect(payload).not.toHaveProperty('id');
        expect(payload).not.toHaveProperty('created_at');
        expect(payload).not.toHaveProperty('updated_at');
    });
});
