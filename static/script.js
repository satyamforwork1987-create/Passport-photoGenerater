const photoInput = document.getElementById('photoInput');
const uploadBox = document.getElementById('uploadBox');
const uploadText = document.getElementById('uploadText');
const originalPreview = document.getElementById('originalPreview');
const processedPreview = document.getElementById('processedPreview');
const processingSpinner = document.getElementById('processingSpinner');
const previewError = document.getElementById('previewError');
const generateError = document.getElementById('generateError');
const generateBtn = document.getElementById('generateBtn');
const sizeSelect = document.getElementById('sizeSelect');
const quantityInput = document.getElementById('quantityInput');

let selectedFile = null;

function getSelectedColor() {
  const checked = document.querySelector('input[name="color"]:checked');
  return checked ? checked.value : 'white';
}

function resetMessages() {
  previewError.textContent = '';
  generateError.textContent = '';
}

async function runPreview() {
  if (!selectedFile) return;
  resetMessages();
  processedPreview.removeAttribute('src');
  processingSpinner.hidden = false;
  generateBtn.disabled = true;

  const formData = new FormData();
  formData.append('photo', selectedFile);
  formData.append('color', getSelectedColor());

  try {
    const res = await fetch('/preview', { method: 'POST', body: formData });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || 'Failed to process photo.');
    }
    const blob = await res.blob();
    processedPreview.src = URL.createObjectURL(blob);
    generateBtn.disabled = false;
  } catch (err) {
    previewError.textContent = err.message;
  } finally {
    processingSpinner.hidden = true;
  }
}

photoInput.addEventListener('change', () => {
  const file = photoInput.files[0];
  if (!file) return;
  selectedFile = file;
  uploadBox.classList.add('has-file');
  uploadText.textContent = file.name;
  originalPreview.src = URL.createObjectURL(file);
  runPreview();
});

document.querySelectorAll('input[name="color"]').forEach((el) => {
  el.addEventListener('change', runPreview);
});

generateBtn.addEventListener('click', async () => {
  if (!selectedFile) return;
  resetMessages();
  generateBtn.disabled = true;
  generateBtn.textContent = 'Generating...';

  const formData = new FormData();
  formData.append('photo', selectedFile);
  formData.append('color', getSelectedColor());
  formData.append('size', sizeSelect.value);
  formData.append('quantity', quantityInput.value || '8');

  try {
    const res = await fetch('/generate', { method: 'POST', body: formData });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || 'Failed to generate photo sheet.');
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'passport_photos.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    generateError.textContent = err.message;
  } finally {
    generateBtn.disabled = false;
    generateBtn.textContent = 'Generate & Download A4 PDF';
  }
});
