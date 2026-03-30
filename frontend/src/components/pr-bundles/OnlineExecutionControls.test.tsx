import { render } from '@testing-library/react';
import { OnlineExecutionControls } from '@/components/pr-bundles/OnlineExecutionControls';

describe('OnlineExecutionControls', () => {
  it('renders nothing', () => {
    const { container } = render(<OnlineExecutionControls />);
    expect(container.firstChild).toBeNull();
  });
});
