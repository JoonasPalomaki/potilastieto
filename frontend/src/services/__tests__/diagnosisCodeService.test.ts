import { afterEach, describe, expect, it, vi } from 'vitest';

import { diagnosisCodeService } from '../diagnosisCodeService';

describe('diagnosisCodeService', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('uploads CSV files under the csv_file field', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ imported: 1 }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const appendSpy = vi.spyOn(FormData.prototype, 'append');

    const file = new File(['code,description'], 'codes.csv', { type: 'text/csv' });

    await diagnosisCodeService.importCodes({
      file,
      authorization: 'Bearer token',
    });

    expect(appendSpy).toHaveBeenCalledWith('csv_file', file, 'codes.csv');
    expect(fetchMock).toHaveBeenCalled();
  });
});
