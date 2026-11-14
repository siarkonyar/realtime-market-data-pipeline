import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from '../../../frontend/src/App'

describe('App', () => {
  it('shows the page title', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'Market data' })).toBeInTheDocument()
  })
})
