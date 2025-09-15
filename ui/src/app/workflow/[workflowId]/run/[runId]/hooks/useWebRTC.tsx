import { useRef, useState } from "react";

import { offerApiV1PipecatRtcOfferPost, validateUserConfigurationsApiV1UserConfigurationsUserValidateGet, validateWorkflowApiV1WorkflowWorkflowIdValidatePost } from "@/client/sdk.gen";
import { WorkflowValidationError } from "@/components/flow/types";
import logger from '@/lib/logger';
import { getRandomId } from "@/lib/utils";

import { sdpFilterCodec } from "../utils";
import { useDeviceInputs } from "./useDeviceInputs";

interface UseWebRTCProps {
    workflowId: number;
    workflowRunId: number;
    accessToken: string | null;
    initialContextVariables?: Record<string, string> | null;
}

export const useWebRTC = ({ workflowId, workflowRunId, accessToken, initialContextVariables }: UseWebRTCProps) => {
    const [connectionStatus, setConnectionStatus] = useState<'idle' | 'connecting' | 'connected' | 'failed'>('idle');
    const [connectionActive, setConnectionActive] = useState(false);
    const [isCompleted, setIsCompleted] = useState(false);
    const [apiKeyModalOpen, setApiKeyModalOpen] = useState(false);
    const [apiKeyError, setApiKeyError] = useState<string | null>(null);
    const [workflowConfigModalOpen, setWorkflowConfigModalOpen] = useState(false);
    const [workflowConfigError, setWorkflowConfigError] = useState<string | null>(null);
    const [isStarting, setIsStarting] = useState(false);
    // Use initial context variables directly, no UI for editing
    const initialContext = initialContextVariables || {};

    const {
        audioInputs,
        selectedAudioInput,
        setSelectedAudioInput,
        permissionError,
        setPermissionError
    } = useDeviceInputs();

    const useStun = true;
    const useAudio = true;
    const audioCodec = 'default';

    const audioRef = useRef<HTMLAudioElement>(null);
    const pcRef = useRef<RTCPeerConnection | null>(null);
    const timeStartRef = useRef<number | null>(null);
    const pc_id = 'PC-' + getRandomId().toString();

    const createPeerConnection = () => {
        const config: RTCConfiguration = {
            iceServers: useStun ? [{ urls: ['stun:stun.l.google.com:19302'] }] : []
        };

        const pc = new RTCPeerConnection(config);

        pc.addEventListener('icegatheringstatechange', () => {
            logger.info(`ICE gathering state changed in createPeerConnection, ${pc.iceGatheringState}`);
        });

        pc.addEventListener('iceconnectionstatechange', () => {
            logger.info(`ICE connection state changed: ${pc.iceConnectionState}`);
            if (pc.iceConnectionState === 'connected' || pc.iceConnectionState === 'completed') {
                setConnectionStatus('connected');
            } else if (pc.iceConnectionState === 'failed' || pc.iceConnectionState === 'disconnected') {
                setConnectionStatus('failed');
            }
        });

        pc.addEventListener('track', (evt) => {
            if (evt.track.kind === 'audio' && audioRef.current) {
                audioRef.current.srcObject = evt.streams[0];
            }
        });

        pcRef.current = pc;
        return pc;
    };

    const negotiate = async () => {
        const pc = pcRef.current;
        if (!pc) return;

        try {
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);

            await new Promise<void>((resolve) => {
                if (pc.iceGatheringState === 'complete') {
                    resolve();
                } else {
                    const checkState = () => {
                        if (pc.iceGatheringState === 'complete') {
                            logger.debug(`ICE gathering is complete in negotiate, ${pc.iceGatheringState}`);
                            pc.removeEventListener('icegatheringstatechange', checkState);
                            resolve();
                        }
                    };
                    pc.addEventListener('icegatheringstatechange', checkState);
                }
            });

            const localDescription = pc.localDescription;
            if (!localDescription) return;

            let sdp = localDescription.sdp;

            if (audioCodec !== 'default') {
                sdp = sdpFilterCodec('audio', audioCodec, sdp);
            }

            if (!accessToken) return;

            const response = await offerApiV1PipecatRtcOfferPost({
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
                body: {
                    sdp: sdp,
                    type: 'offer',
                    pc_id: pc_id,
                    restart_pc: false,
                    workflow_id: workflowId,
                    workflow_run_id: workflowRunId,
                    call_context_vars: initialContext
                }
            });

            if (response && response.data) {
                const answerSdpText = typeof response.data === 'object' && 'sdp' in response.data
                    ? response.data.sdp as string
                    : '';

                await pc.setRemoteDescription({
                    type: 'answer',
                    sdp: answerSdpText
                });
                setConnectionActive(true);
            }
        } catch (e) {
            logger.error(`Negotiation failed: ${e}`);
        }
    };

    const start = async () => {
        if (isStarting || !accessToken) return;
        setIsStarting(true);
        setConnectionStatus('connecting');
        try {
            const response = await validateUserConfigurationsApiV1UserConfigurationsUserValidateGet({
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
                query: {
                    validity_ttl_seconds: 86400
                },
            });
            if (response.error) {
                setApiKeyModalOpen(true);
                let msg = 'API Key Error';
                const detail = (response.error as unknown as { detail?: { errors: { model: string; message: string }[] } }).detail;
                if (Array.isArray(detail)) {
                    msg = detail
                        .map((e: { model: string; message: string }) => `${e.model}: ${e.message}`)
                        .join('\n');
                }
                setApiKeyError(msg);
                return;
            }

            // Then check workflow validation
            const workflowResponse = await validateWorkflowApiV1WorkflowWorkflowIdValidatePost({
                path: {
                    workflow_id: workflowId,
                },
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            });

            if (workflowResponse.error) {
                setWorkflowConfigModalOpen(true);
                let msg = 'Workflow validation failed';
                const errorDetail = workflowResponse.error as { detail?: { errors: WorkflowValidationError[] } };
                if (errorDetail?.detail?.errors) {
                    msg = errorDetail.detail.errors
                        .map(err => `${err.kind}: ${err.message}`)
                        .join('\n');
                }
                setWorkflowConfigError(msg);
                return;
            }

            timeStartRef.current = null;
            const pc = createPeerConnection();

            const constraints: MediaStreamConstraints = {
                audio: false,
            };

            if (useAudio) {
                const audioConstraints: MediaTrackConstraints = {};
                if (selectedAudioInput) {
                    audioConstraints.deviceId = { exact: selectedAudioInput };
                }
                constraints.audio = Object.keys(audioConstraints).length ? audioConstraints : true;
            }

            if (constraints.audio) {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia(constraints);
                    stream.getTracks().forEach((track) => {
                        pc.addTrack(track, stream);
                    });
                    await negotiate();
                } catch (err) {
                    logger.error(`Could not acquire media: ${err}`);
                    setPermissionError('Could not acquire media');
                    setConnectionStatus('failed');
                }
            } else {
                await negotiate();
            }
        } finally {
            setIsStarting(false);
        }
    };

    const stop = () => {
        setConnectionActive(false);
        setIsCompleted(true);
        setConnectionStatus('idle');

        const pc = pcRef.current;
        if (!pc) return;

        if (pc.getTransceivers) {
            pc.getTransceivers().forEach((transceiver) => {
                if (transceiver.stop) {
                    transceiver.stop();
                }
            });
        }

        pc.getSenders().forEach((sender) => {
            if (sender.track) {
                sender.track.stop();
            }
        });

        setTimeout(() => {
            if (pcRef.current) {
                pcRef.current.close();
                pcRef.current = null;
            }
        }, 500);
    };

    return {
        audioRef,
        audioInputs,
        selectedAudioInput,
        setSelectedAudioInput,
        connectionActive,
        permissionError,
        isCompleted,
        apiKeyModalOpen,
        setApiKeyModalOpen,
        apiKeyError,
        workflowConfigError,
        workflowConfigModalOpen,
        setWorkflowConfigModalOpen,
        connectionStatus,
        start,
        stop,
        isStarting,
        initialContext
    };
};
