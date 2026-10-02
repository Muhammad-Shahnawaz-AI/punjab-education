import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { WorkspacePlaceholder } from './WorkspacePlaceholder';

describe('WorkspacePlaceholder', () => {
  it('shows the route title and current feature status', () => {
    render(
      <WorkspacePlaceholder
        title="Curriculum"
        description="Explore curriculum topics."
      />,
    );

    expect(screen.getByRole('heading', { name: 'Curriculum' })).toBeInTheDocument();
    expect(screen.getByText('Feature in progress')).toBeInTheDocument();
  });
});