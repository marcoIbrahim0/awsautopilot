import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ExplainerHint } from '@/components/ui/ExplainerHint';

describe('ExplainerHint', () => {
  it('shows registry-backed content on hover and uses an accessible label', async () => {
    const user = userEvent.setup();

    render(
      <ExplainerHint
        content={{ conceptId: 'remediation_strategy', context: 'remediation' }}
        label="Remediation strategy"
        iconOnly
      />,
    );

    const trigger = screen.getByRole('button', { name: 'Show contextual help' });
    await user.hover(trigger);

    expect(await screen.findByRole('tooltip')).toHaveTextContent(
      'This is the specific path the platform recommends for handling the action.',
    );
  });
});
