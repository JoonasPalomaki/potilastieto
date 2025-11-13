import { describe, expect, it } from 'vitest';

import { ApiError } from '../../services/visitService';
import { resolveApiErrorMessage } from '../apiErrors';

describe('resolveApiErrorMessage', () => {
  it('palauttaa palvelimen viestin sellaisenaan', () => {
    const error = new ApiError('Request failed', 400, { detail: 'Virheellinen pyyntö' });

    expect(resolveApiErrorMessage(error)).toBe('Virheellinen pyyntö');
  });

  it('jäsentää FastAPI:n validointivirheet', () => {
    const error = new ApiError('Request failed', 422, {
      detail: [
        { loc: ['body', 'identifier'], msg: 'Henkilötunnus on jo käytössä' },
        { loc: ['body', 'first_name'], msg: 'Etunimi puuttuu' },
      ],
    });

    expect(resolveApiErrorMessage(error)).toBe(
      'identifier: Henkilötunnus on jo käytössä first_name: Etunimi puuttuu',
    );
  });
});
