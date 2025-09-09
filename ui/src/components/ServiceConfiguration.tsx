"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { getDefaultConfigurationsApiV1UserConfigurationsDefaultsGet } from '@/client/sdk.gen';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useUserConfig } from "@/context/UserConfigContext";

type ServiceSegment = "llm" | "tts" | "stt";

interface SchemaProperty {
    type?: string;
    default?: string | number | boolean;
    enum?: string[];
    $ref?: string;
    description?: string;
    format?: string;
}

interface ProviderSchema {
    properties: Record<string, SchemaProperty>;
    required?: string[];
    $defs?: Record<string, SchemaProperty>;
    [key: string]: unknown;
}

interface FormValues {
    [key: string]: string | number | boolean;
}

export default function ServiceConfiguration() {
    const [apiError, setApiError] = useState<string | null>(null);
    const [isSaving, setIsSaving] = useState(false);
    const { userConfig, saveUserConfig } = useUserConfig();
    const [schemas, setSchemas] = useState<Record<ServiceSegment, Record<string, ProviderSchema>>>({
        llm: {},
        tts: {},
        stt: {}
    });
    const [serviceProviders, setServiceProviders] = useState<Record<ServiceSegment, string>>({
        llm: "",
        tts: "",
        stt: ""
    });

    const {
        register,
        handleSubmit,
        formState: { errors },
        reset,
        getValues,
        setValue,
        watch
    } = useForm();

    useEffect(() => {
        const fetchConfigurations = async () => {
            const response = await getDefaultConfigurationsApiV1UserConfigurationsDefaultsGet();
            if (response.data) {
                setSchemas({
                    llm: response.data.llm as Record<string, ProviderSchema>,
                    tts: response.data.tts as Record<string, ProviderSchema>,
                    stt: response.data.stt as Record<string, ProviderSchema>
                });
            } else {
                console.error("Failed to fetch configurations");
                return;
            }

            const defaultValues: Record<string, string | number | boolean> = {};
            const selectedProviders: Record<ServiceSegment, string> = {
                llm: response.data.default_providers.llm,
                tts: response.data.default_providers.tts,
                stt: response.data.default_providers.stt
            };

            const setServicePropertyValues = (service: ServiceSegment) => {
                /*
                    sets service properties like api_key, model etc. from default configurations
                    if not present in user configurations

                    service - llm/ tts/ stt


                    userConfig['llm'] = {
                        provider: 'openai',
                        api_key: 'sk-...'
                    }

                    response.data.llm = {
                        openai: {
                            properties: {
                                provider: 'openai'
                                api_key: 'sk-...'
                            }
                        }
                    }
                */

                if (userConfig?.[service]?.provider) {
                    Object.entries(userConfig?.[service]).forEach(([field, value]) => {
                        if (field !== "provider") {
                            defaultValues[`${service}_${field}`] = value;
                        }
                    });
                    selectedProviders[service] = userConfig?.[service]?.provider as string;
                } else {
                    // response.data['service'] will all providers for the given service
                    // selectedProviders[service] will have the provider name
                    const properties = response.data[service]?.[selectedProviders[service]]?.properties as Record<string, SchemaProperty>;
                    if (properties) {
                        Object.entries(properties).forEach(([field, schema]) => {
                            if (field !== "provider" && schema.default) {
                                defaultValues[`${service}_${field}`] = schema.default;
                            }
                        });
                    }
                }
            }

            setServicePropertyValues("llm");
            setServicePropertyValues("tts");
            setServicePropertyValues("stt");

            setServiceProviders(selectedProviders);

            reset(defaultValues);
        };
        fetchConfigurations();
    }, [reset, userConfig]);

    const handleProviderChange = (service: ServiceSegment, providerName: string) => {
        /*
            service can be llm/ tts/ stt
            providerName is openAI/ Deepgram etc.
        */
        if (!providerName) {
            return;
        }

        const currentValues = getValues();
        const preservedValues: Record<string, string | number | boolean> = {};

        // Preserve values from other services
        Object.keys(currentValues).forEach(key => {
            if (!key.startsWith(`${service}_`)) {
                preservedValues[key] = currentValues[key];
            }
        });

        // Set default values from schema
        if (schemas?.[service]?.[providerName]) {
            const providerSchema = schemas[service][providerName];
            Object.entries(providerSchema.properties).forEach(([field, schema]: [string, SchemaProperty]) => {
                if (field !== "provider" && schema.default !== undefined) {
                    preservedValues[`${service}_${field}`] = schema.default;
                }
            });
        }

        preservedValues[`${service}_provider`] = providerName;
        reset(preservedValues);
        setServiceProviders(prev => ({ ...prev, [service]: providerName }));
    }


    const onSubmit = async (data: FormValues) => {
        /*
            data contains form values like llm_api_key: "sk...", llm_model: "gpt-4o" etc.
            extract the values in relevant form
        */
        setApiError(null);
        setIsSaving(true);

        const userConfig = {
            llm: {
                provider: serviceProviders.llm,
                api_key: data.llm_api_key as string,
                model: data.llm_model as string
            },
            tts: {
                provider: serviceProviders.tts,
                api_key: data.tts_api_key as string
            },
            stt: {
                provider: serviceProviders.stt,
                api_key: data.stt_api_key as string
            }
        };

        // Add any extra properties in the payload
        Object.entries(data).forEach(([property, value]) => {
            const parts = property.split('_');
            const service = parts[0] as ServiceSegment;
            const field = parts.slice(1).join('_'); // Join all parts after the service name

            if (userConfig[service] && !(field in userConfig[service])) {
                (userConfig[service] as Record<string, string>)[field] = value as string;
            }
        });

        try {
            await saveUserConfig({
                llm: userConfig.llm,
                tts: userConfig.tts,
                stt: userConfig.stt
            });
            setApiError(null);
        } catch (error: unknown) {
            if (error instanceof Error) {
                setApiError(error.message);
            } else {
                setApiError('An unknown error occurred');
            }
        } finally {
            setIsSaving(false);
        }
    };

    const renderServiceSegmentFields = (service: ServiceSegment) => {
        // Segment is segments like llm, tts and stt
        const currentProvider = serviceProviders[service];
        const providerSchema = schemas?.[service]?.[currentProvider];
        const availableProviders = schemas?.[service] ? Object.keys(schemas[service]) : [];

        return (
            <Card className="mb-6">
                <CardHeader>
                    <CardTitle>{service.toUpperCase()} Configuration</CardTitle>
                    <CardDescription>
                        Configure your {service.toUpperCase()} service
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <Label>Provider</Label>
                            <Select
                                value={currentProvider}
                                onValueChange={(providerName) => {
                                    handleProviderChange(service, providerName);
                                }}
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder={`Select ${service.toUpperCase()} provider`} />
                                </SelectTrigger>
                                <SelectContent>
                                    {availableProviders.map((provider) => (
                                        <SelectItem key={provider} value={provider}>
                                            {provider}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        {currentProvider && providerSchema && (
                            <div className="space-y-4">
                                {Object.entries(providerSchema.properties).map(([field, schema]: [string, SchemaProperty]) => {
                                    // Handle $ref fields by getting the actual schema from $defs
                                    const actualSchema = schema.$ref && providerSchema.$defs
                                        ? providerSchema.$defs[schema.$ref.split('/').pop() || '']
                                        : schema;

                                    // Skip provider field as it's handled separately
                                    return field !== "provider" && (
                                        <div key={`${service}_${field}_${currentProvider}`} className="space-y-2">
                                            <Label>{field}</Label>
                                            {actualSchema?.enum ? (
                                                <Select
                                                    value={watch(`${service}_${field}`) as string || ""}
                                                    onValueChange={(value) => {
                                                        setValue(`${service}_${field}`, value, { shouldDirty: true });
                                                    }}
                                                >
                                                    <SelectTrigger>
                                                        <SelectValue placeholder={`Select ${field}`} />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {actualSchema.enum.map((value: string) => (
                                                            <SelectItem key={value} value={value}>
                                                                {value}
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            ) : (
                                                <Input
                                                    type={actualSchema?.type === "number" ? "number" : "text"}
                                                    {...(actualSchema?.type === "number" && { step: "any" })}
                                                    placeholder={`Enter ${field}`}
                                                    {...register(`${service}_${field}`, {
                                                        required: providerSchema.required?.includes(field),
                                                        valueAsNumber: actualSchema?.type === "number"
                                                    })}
                                                />
                                            )}
                                            {errors[`${service}_${field}`] && (
                                                <p className="text-sm text-red-500">
                                                    {typeof errors[`${service}_${field}`]?.message === 'string'
                                                        ? String(errors[`${service}_${field}`]?.message)
                                                        : "This field is required"}
                                                </p>
                                            )}
                                        </div>
                                    );
                                })}

                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>
        );
    };


    return (
        <div className="w-full max-w-4xl mx-auto py-8">
            <h1 className="text-2xl font-bold mb-6">Service Configuration</h1>

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
                {renderServiceSegmentFields("llm")}
                {renderServiceSegmentFields("tts")}
                {renderServiceSegmentFields("stt")}

                {apiError && <p className="text-red-500">{apiError}</p>}

                <Button type="submit" className="w-full" disabled={isSaving}>
                    {isSaving ? "Saving..." : "Save Configuration"}
                </Button>
            </form>
        </div>
    );
}
