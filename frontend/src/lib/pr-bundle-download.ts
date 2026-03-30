/**
 * PR bundle download (Step 9.6).
 * Builds a zip from run.artifacts.pr_bundle.files and triggers download as pr-bundle-{runId}.zip.
 */

import JSZip from 'jszip';

export interface PrBundleFile {
  path: string;
  content: string;
}

const ZIP_FILENAME_PREFIX = 'pr-bundle';

/**
 * Build a zip blob from PR bundle files and trigger browser download.
 * Files are stored at root of the zip (e.g. main.tf, s3_block_public_access.tf).
 *
 * @param runId - Remediation run ID (used for filename pr-bundle-{runId}.zip)
 * @param files - List of { path, content } from artifacts.pr_bundle.files
 */
export async function downloadPrBundleZip(
  runId: string,
  files: PrBundleFile[]
): Promise<void> {
  if (!files?.length) {
    throw new Error('No files to download');
  }

  const zip = new JSZip();
  for (const f of files) {
    const name = (f.path || '').trim() || 'file';
    zip.file(name, f.content ?? '');
  }

  const blob = await zip.generateAsync({ type: 'blob' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${ZIP_FILENAME_PREFIX}-${runId}.zip`;
  link.click();
  URL.revokeObjectURL(url);
}
