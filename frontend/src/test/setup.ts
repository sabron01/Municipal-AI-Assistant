import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
  document.cookie = 'maa_csrf=; Max-Age=0; path=/'
  document.cookie = '__Host-maa_csrf=; Max-Age=0; path=/'
})
