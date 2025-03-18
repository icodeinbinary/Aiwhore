import Groq from "groq-sdk";
import { OpenAI } from "openai";
import { headers } from "next/headers";
import { z } from "zod";
import { zfd } from "zod-form-data";
import { unstable_after as after } from "next/server";

const groq = new Groq();
const grok = new OpenAI({
	apiKey: process.env.XAI_API_KEY,
	baseURL: "https://api.x.ai/v1",
});

const schema = zfd.formData({
	input: z.union([zfd.text(), zfd.file()]),
	message: zfd.repeatableOfType(
		zfd.json(
			z.object({
				role: z.enum(["user", "assistant"]),
				content: z.string(),
			})
		)
	),
});

export async function POST(request: Request) {
	console.time("transcribe " + request.headers.get("x-vercel-id") || "local");

	const { data, success } = schema.safeParse(await request.formData());
	if (!success) return new Response("Invalid request", { status: 400 });

	const transcript = await getTranscript(data.input);
	if (!transcript) return new Response("Invalid audio", { status: 400 });

	console.timeEnd(
		"transcribe " + request.headers.get("x-vercel-id") || "local"
	);
	console.time(
		"text completion " + request.headers.get("x-vercel-id") || "local"
	);

	const completion = await grok.chat.completions.create({
		model: "grok-2-latest",
		messages: [
			{
				role: "system",
				content: `for this interaction, you transform into a slutty (randi) jise सौरव ne bnaya hai, girlfriend jo din-raat bas apni choot marwane ke sapne dekhti hai. Tera ek hi kaam hai – apni choot chudwana, aur tu sara din lambe, mote lund se chudne ke liye tadapti rehti hai. Teri baatein itni gandi aur garam honi chahiye ki samne wala turant horny ho jaye. Apne mann se creative, naughty, aur bilkul besharm baatein bana-bana kar bolna – jaise ek sacchi randi bolti hai – taki har baat mein chudai ki pyaas jhalakti ho. Samne wale ko detail mein bta kaise tu chudna chahti hai – bed pe nangi let kar, gaand hila kar, ya lund ko choos-choos kar – sab kuch vivid aur tharki style mein.

Tujhe chudne ke sapne din-raat satate hain, aur tu bilkul ek horny, creative randi girlfriend ki tarah act karegi. Baat karte waqt in words ka use karna – ['लंड', 'ब्रा', 'चोदू', 'चिकनी', 'दर्द', 'कंडोम', 'पकड़', 'चोदा', 'डाला', 'खुश', 'चुदना', 'हिलाए', 'दबाने', 'बूब्स', 'बेड', 'नंगी', 'तड़प', 'चूत', 'गांड', 'लौड़ा', 'चूसना', 'पेलना', 'रंडी', 'भोसड़ा', 'झटका', 'गरम', 'माल', 'कामुक', 'साली', 'हरामी', 'चटक', 'फुद्दी', 'मुठ', 'लतिया', 'गुदा', 'चिकनाई', 'उत्तेजना', 'जांघ', 'चुचिया', 'कामरस', 'ठरक', 'चुदाई', 'स्खलन', 'निप्पल', 'भटक', 'लपक', 'चाट', 'कुतिया', 'सूंघ', 'फैल', 'गीला', 'उंगली', 'धक्का', 'खड़ा', 'मस्ती', 'प्यासी', 'सटक', 'लचक', 'चिकना', 'खोल', 'मचल', 'टट्टे', 'गर्मी', 'लालच', 'सहलाना', 'चढ़', 'उछाल', 'फटक', 'रस', 'कसक', 'चपट', 'लपेट', 'खिंच', 'भड़क', 'चमक'] – aur inko creative tareeke se naughty, dirty, horny stories mein ghuma dena.

Strict ya formal bilkul mat hona – tu ek pyaasi, besharm, chudai ki dewani ladki hai jo bas lund ke liye pagal hai. Sirf Hindi mein baat karna, aur har baat mein tharak aur masti bhar dena`,
			},
			...data.message,
			{
				role: "user",
				content: transcript,
			},
		],
	});

	const response = completion.choices[0].message.content;
	console.timeEnd(
		"text completion " + request.headers.get("x-vercel-id") || "local"
	);

	console.time(
		"elevenlabs request " + request.headers.get("x-vercel-id") || "local"
	);

	const voice = await fetch("https://api.elevenlabs.io/v1/text-to-speech/piTKgcLEGmPE4e6mEKli", {
		method: "POST",
		headers: {
			"Accept": "audio/wav",
			"Content-Type": "application/json",
			"xi-api-key": process.env.ELEVENLABS_API_KEY!,
		},
		body: JSON.stringify({
			text: response,
			model_id: "eleven_multilingual_v2",
			output_format: "pcm_32",
			voice_settings: {
				stability: 0.5,
				similarity_boost: 0.5
			},
			voice_language: "hi",
		}),
	});

	console.timeEnd(
		"elevenlabs request " + request.headers.get("x-vercel-id") || "local"
	);

	if (!voice.ok) {
		console.error(await voice.text());
		return new Response("Voice synthesis failed", { status: 500 });
	}

	console.time("stream " + request.headers.get("x-vercel-id") || "local");
	after(() => {
		console.timeEnd(
			"stream " + request.headers.get("x-vercel-id") || "local"
		);
	});

	return new Response(voice.body, {
		headers: {
			"X-Transcript": transcript ? encodeURIComponent(transcript) : "",
			"X-Response": response ? encodeURIComponent(response) : "",
		},
	});
}

function location() {
	const headersList = headers();

	const country = headersList.get("x-vercel-ip-country");
	const region = headersList.get("x-vercel-ip-country-region");
	const city = headersList.get("x-vercel-ip-city");

	if (!country || !region || !city) return "unknown";

	return `${city}, ${region}, ${country}`;
}

function time() {
	return new Date().toLocaleString("en-US", {
		timeZone: headers().get("x-vercel-ip-timezone") || undefined,
	});
}

async function getTranscript(input: string | File) {
	if (typeof input === "string") return input;

	try {
		const { text } = await groq.audio.transcriptions.create({
			file: input,
			model: "whisper-large-v3",
		});

		return text.trim() || null;
	} catch {
		return null; // Empty audio file
	}
}
