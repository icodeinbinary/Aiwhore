import { useRef, useState } from "react";

export function usePlayer() {
	const [isPlaying, setIsPlaying] = useState(false);
	const audioContext = useRef<AudioContext | null>(null);
	const source = useRef<AudioBufferSourceNode | null>(null);
	const audioElement = useRef<HTMLAudioElement | null>(null);

	async function play(stream: ReadableStream, callback: () => void) {
		stop();
		
		try {
			// Try first using MediaSource for MP3/compressed formats
			const audio = new Audio();
			audioElement.current = audio;
			
			// Convert stream to blob
			const response = new Response(stream);
			const blob = await response.blob();
			const url = URL.createObjectURL(blob);
			
			audio.src = url;
			audio.onended = () => {
				stop();
				callback();
			};
			
			setIsPlaying(true);
			audio.play().catch(async (err) => {
				console.error("Error playing audio, falling back to Web Audio API:", err);
				
				// Fallback to PCM processing if MediaSource fails
				const arrayBuffer = await blob.arrayBuffer();
				const sampleRate = 24000; // ElevenLabs uses 24kHz
				
				audioContext.current = new AudioContext({ sampleRate });
				audioContext.current.decodeAudioData(arrayBuffer, (audioBuffer) => {
					source.current = audioContext.current!.createBufferSource();
					source.current.buffer = audioBuffer;
					source.current.connect(audioContext.current!.destination);
					source.current.onended = () => {
						stop();
						callback();
					};
					source.current.start();
				}, (err) => {
					console.error("Error decoding audio:", err);
					stop();
					callback();
				});
			});
		} catch (error) {
			console.error("Error playing audio:", error);
			stop();
			callback();
		}
	}

	function stop() {
		if (audioElement.current) {
			audioElement.current.pause();
			audioElement.current.src = "";
			audioElement.current = null;
		}
		
		if (source.current) {
			source.current.stop();
			source.current = null;
		}
		
		if (audioContext.current) {
			audioContext.current.close();
			audioContext.current = null;
		}
		
		setIsPlaying(false);
	}

	return {
		isPlaying,
		play,
		stop,
	};
}
