import { AUDIO, IMAGE, VIDEO } from './api.js'

/** Etiqueta corta del tipo de archivo y su clave (para colorear). */
export const typeTag = (ext) => (ext === 'pdf' ? 'pdf' : AUDIO.includes(ext) ? 'aud' : VIDEO.includes(ext) ? 'vid' : IMAGE.includes(ext) ? 'img' : 'txt')
export const typeLabel = (ext) => (ext === 'pdf' ? 'PDF' : AUDIO.includes(ext) ? 'Audio' : VIDEO.includes(ext) ? 'Video' : IMAGE.includes(ext) ? 'Imagen' : 'Texto')
