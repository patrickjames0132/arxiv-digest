// @vitest-environment jsdom
/**
 * The color legend never explains marks that aren't on screen: the five
 * relation entries are static, the two agent entries appear on first use.
 */

import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import Legend from '../../../src/graph/controls/Legend'

describe('Legend', () => {
  it('always shows the five relation entries', () => {
    render(<Legend hasDiscovered={false} hasSearchHits={false} />)
    for (const label of [
      'Seed',
      'References',
      'Field Landmarks',
      'Latest Publications',
      'Similar',
    ]) {
      expect(screen.getByText(label)).toBeTruthy()
    }
  })

  it('hides the agent entries until the agent has actually acted', () => {
    render(<Legend hasDiscovered={false} hasSearchHits={false} />)
    expect(screen.queryByText('Discovered by teacher')).toBeNull()
    expect(screen.queryByText('Found by search')).toBeNull()
  })

  it('shows each agent entry once its flag flips', () => {
    render(<Legend hasDiscovered={true} hasSearchHits={true} />)
    expect(screen.getByText('Discovered by teacher')).toBeTruthy()
    expect(screen.getByText('Found by search')).toBeTruthy()
  })
})
