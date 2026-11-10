import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { JamaRequirement } from '@/types/api';
import { normalizeRequirementText } from '@/radia_ai/features/jamaRequirementReviewer/utils/requirementNormalization';
import RequirementReview from './RequirementReview';

const jama = vi.hoisted(() => ({
  search: vi.fn(),
  requirement: vi.fn(),
}));

vi.mock('@/radia_ai/features/jamaRequirementReviewer/hooks/useJama', () => ({
  JAMA_LINK_REQUIRED_CODES: new Set(),
  jamaErrorCode: () => undefined,
  useJamaProjects: () => ({ data: { projects: [{ id: 7, name: 'Aircraft' }] } }),
  useJamaRequirementSearch: jama.search,
  useJamaRequirement: jama.requirement,
}));

vi.mock('@/radia_ai/features/jamaRequirementReviewer/hooks/useRequirementReview', () => ({
  useRequirementReview: () => ({ mutate: vi.fn(), reset: vi.fn(), isPending: false }),
}));

vi.mock('@/radia_ai/features/jamaRequirementReviewer/hooks/useReviewHistory', () => ({
  useApplyFindingDisposition: () => ({ mutate: vi.fn() }),
  useApplyRecommendationDecision: () => ({ mutate: vi.fn() }),
  useWriteDecisionToJama: () => ({ mutate: vi.fn(), reset: vi.fn() }),
}));

vi.mock('@/hooks/useNavigationGuard', () => ({ useNavigationGuard: vi.fn() }));
vi.mock('@/radia_ai/features/jamaRequirementReviewer/components/FileUploadZone', () => ({
  FileUploadZone: () => <div>File upload</div>,
}));
vi.mock('@/hooks/useReviewCompleteSound', () => ({ useReviewCompleteSound: () => vi.fn() }));
vi.mock('@/context/useNavigationGuardContext', () => ({
  useNavigationGuardContext: () => ({ guardedNavigate: vi.fn() }),
}));

const requirement: JamaRequirement = {
  id: 42,
  document_key: 'REQ-42',
  global_id: null,
  name: 'Operational Requirements',
  description: 'The aircraft shall report its status.',
  rationale: '',
  status: null,
  item_type_id: null,
  project_id: 7,
  created_date: null,
  modified_date: null,
  web_url: 'https://example.jamacloud.com/items/42',
  fields: {},
};

describe('Individual Requirement Review - retained Jama input', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    jama.search.mockReset();
    jama.requirement.mockReset();
    jama.search.mockReturnValue({ data: { results: [requirement] } });
    jama.requirement.mockImplementation((id: number | null) => ({
      data: id === requirement.id ? requirement : undefined,
    }));
  });

  it('retains a pasted search name across input-tab switches, blur, and page remounts', async () => {
    const first = render(<RequirementReview />);
    fireEvent.click(screen.getByRole('button', { name: 'From Jama' }));
    fireEvent.change(screen.getByRole('combobox', { name: 'Search Jama requirements' }), {
      target: { value: 'Operational Requirements' },
    });
    fireEvent.blur(screen.getByRole('combobox', { name: 'Search Jama requirements' }));
    expect(screen.getByRole('combobox', { name: 'Search Jama requirements' }))
      .toHaveValue('Operational Requirements');

    fireEvent.click(screen.getByRole('button', { name: 'Type / Paste' }));
    fireEvent.click(screen.getByRole('button', { name: 'From Jama' }));
    expect(screen.getByRole('combobox', { name: 'Search Jama requirements' }))
      .toHaveValue('Operational Requirements');
    await waitFor(() => expect(jama.search).toHaveBeenLastCalledWith(
      expect.objectContaining({ contains: 'Operational Requirements' }),
    ));

    first.unmount();
    render(<RequirementReview />);
    expect(screen.getByRole('combobox', { name: 'Search Jama requirements' }))
      .toHaveValue('Operational Requirements');
  });

  it('retains the selected requirement and project without replacing edited requirement text', async () => {
    render(<RequirementReview />);
    fireEvent.click(screen.getByRole('button', { name: 'From Jama' }));
    fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Jama project' }));
    fireEvent.click(screen.getByRole('option', { name: 'Aircraft' }));
    const search = screen.getByRole('combobox', { name: 'Search Jama requirements' });
    fireEvent.change(search, { target: { value: 'Operational' } });
    fireEvent.keyDown(search, { key: 'ArrowDown' });
    fireEvent.click(await screen.findByRole('option', { name: /REQ-42/ }));
    const text = await screen.findByLabelText('Requirement text from Jama (sent to AI)');
    fireEvent.change(text, { target: { value: 'Edited requirement text' } });

    fireEvent.click(screen.getByRole('button', { name: 'Upload file' }));
    fireEvent.click(screen.getByRole('button', { name: 'From Jama' }));
    expect(screen.getByRole('combobox', { name: 'Search Jama requirements' }))
      .toHaveValue('REQ-42 — Operational Requirements');
    expect(screen.getByRole('combobox', { name: 'Jama project' })).toHaveTextContent('Aircraft');
    expect(screen.getByLabelText('Requirement text from Jama (sent to AI)'))
      .toHaveValue('Edited requirement text');

    fireEvent.click(screen.getByRole('button', { name: 'Clear Review' }));
    fireEvent.click(screen.getByRole('button', { name: 'From Jama' }));
    expect(screen.getByRole('combobox', { name: 'Search Jama requirements' })).toHaveValue('');
    expect(screen.getByRole('combobox', { name: 'Jama project' })).not.toHaveTextContent('Aircraft');
    expect(screen.queryByLabelText('Requirement text from Jama (sent to AI)')).not.toBeInTheDocument();
  });

  it.each([7, null])('populates the project after selecting a pasted requirement name (search project ID: %s)', async (projectId) => {
    jama.search.mockReturnValue({
      data: { results: [{ ...requirement, project_id: projectId }] },
    });
    jama.requirement.mockReturnValue({ data: undefined });
    const page = render(<RequirementReview />);
    fireEvent.click(screen.getByRole('button', { name: 'From Jama' }));
    const search = screen.getByRole('combobox', { name: 'Search Jama requirements' });
    fireEvent.change(search, { target: { value: requirement.name } });
    fireEvent.keyDown(search, { key: 'ArrowDown' });
    fireEvent.click(await screen.findByRole('option', { name: /REQ-42/ }));

    if (projectId != null) {
      expect(screen.getByRole('combobox', { name: 'Jama project' })).toHaveTextContent('Aircraft');
    } else {
      expect(screen.getByRole('combobox', { name: 'Jama project' })).not.toHaveTextContent('Aircraft');
    }

    jama.requirement.mockImplementation((id: number | null) => ({
      data: id === requirement.id ? requirement : undefined,
    }));
    page.rerender(<RequirementReview />);
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Jama project' }))
      .toHaveTextContent('Aircraft'));
    expect(screen.getByLabelText('Requirement text from Jama (sent to AI)'))
      .toHaveValue(normalizeRequirementText(`Title: ${requirement.name}\n\nDescription: ${requirement.description}`));
    expect(jama.search).toHaveBeenLastCalledWith(expect.objectContaining({ projectId: 7 }));

    fireEvent.click(screen.getByRole('button', { name: 'Upload file' }));
    fireEvent.click(screen.getByRole('button', { name: 'From Jama' }));
    expect(screen.getByRole('combobox', { name: 'Jama project' })).toHaveTextContent('Aircraft');

    fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Jama project' }));
    fireEvent.click(screen.getByRole('option', { name: 'All projects' }));
    expect(jama.search).toHaveBeenLastCalledWith(expect.objectContaining({ projectId: undefined }));
    expect(screen.getByRole('combobox', { name: 'Jama project' })).not.toHaveTextContent('Aircraft');
  });

  it('keeps the project filter when clearing a requirement or selecting one without a project ID', async () => {
    const requirementWithoutProject = { ...requirement, project_id: null };
    jama.search.mockReturnValue({ data: { results: [requirementWithoutProject] } });
    jama.requirement.mockImplementation((id: number | null) => ({
      data: id === requirement.id ? requirementWithoutProject : undefined,
    }));
    render(<RequirementReview />);
    fireEvent.click(screen.getByRole('button', { name: 'From Jama' }));
    fireEvent.mouseDown(screen.getByRole('combobox', { name: 'Jama project' }));
    fireEvent.click(screen.getByRole('option', { name: 'Aircraft' }));
    const search = screen.getByRole('combobox', { name: 'Search Jama requirements' });
    fireEvent.change(search, { target: { value: requirement.name } });
    fireEvent.keyDown(search, { key: 'ArrowDown' });
    fireEvent.click(await screen.findByRole('option', { name: /REQ-42/ }));
    expect(screen.getByRole('combobox', { name: 'Jama project' })).toHaveTextContent('Aircraft');
    fireEvent.click(screen.getByTitle('Clear'));
    expect(search).toHaveValue('');
    expect(screen.getByRole('combobox', { name: 'Jama project' })).toHaveTextContent('Aircraft');
  });

  it('restores older saved forms that have no Jama picker state', () => {
    localStorage.setItem('requirement-review-form-state', JSON.stringify({
      requirementId: '',
      requirementLevel: 'Aircraft',
      text: '',
      inputMode: 'jama',
      uploadedFilename: '',
    }));
    render(<RequirementReview />);
    expect(screen.getByRole('combobox', { name: 'Search Jama requirements' })).toHaveValue('');
  });
});
