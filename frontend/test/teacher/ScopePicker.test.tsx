// @vitest-environment jsdom
/**
 * The scope picker's popover is controlled (`open`/`onOpenChange`) so the
 * assistant header can keep its two pickers mutually exclusive — these tests
 * pin the controlled contract: the popover renders only when told to, the
 * trigger reports a toggle, and the header ✕ reports a close.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import ScopePicker from '../../src/teacher/ScopePicker'

afterEach(cleanup)

const LABELS = {
  icon: '📚',
  unit: 'source',
  heading: 'Search in',
  allHint: 'All sources are searched.',
  someHint: 'Only the checked sources are searched.',
  noneHint: 'No sources selected.',
  buttonTitle: 'Choose sources',
}

const ITEMS = [
  { id: 'a', title: 'First source' },
  { id: 'b', title: 'Second source' },
]

/**
 * Render the picker with inert selection callbacks and the given open state.
 *
 * @param open Whether the popover is shown.
 * @param onOpenChange Spy receiving the requested open state.
 * @returns The RTL render result.
 */
function renderPicker(open: boolean, onOpenChange: (open: boolean) => void) {
  return render(
    <ScopePicker
      items={ITEMS}
      checkedIds={['a', 'b']}
      open={open}
      onOpenChange={onOpenChange}
      onToggle={() => {}}
      onSelectAll={() => {}}
      onDeselectAll={() => {}}
      labels={LABELS}
    />,
  )
}

describe('ScopePicker', () => {
  it('renders the popover only when open (state is the parent’s)', () => {
    const { rerender } = renderPicker(false, () => {})
    expect(screen.queryByText('Search in')).toBeNull()
    rerender(
      <ScopePicker
        items={ITEMS}
        checkedIds={['a', 'b']}
        open={true}
        onOpenChange={() => {}}
        onToggle={() => {}}
        onSelectAll={() => {}}
        onDeselectAll={() => {}}
        labels={LABELS}
      />,
    )
    expect(screen.getByText('Search in')).toBeTruthy()
  })

  it('clicking the trigger requests the opposite open state', () => {
    const onOpenChange = vi.fn()
    renderPicker(false, onOpenChange)
    fireEvent.click(screen.getByText('📚 All sources'))
    expect(onOpenChange).toHaveBeenCalledWith(true)
  })

  it('the popover ✕ requests a close', () => {
    const onOpenChange = vi.fn()
    renderPicker(true, onOpenChange)
    fireEvent.click(screen.getByLabelText('Close the source picker'))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })
})
