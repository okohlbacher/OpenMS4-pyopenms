// --------------------------------------------------------------------------
//                   OpenMS -- Open-Source Mass Spectrometry
// --------------------------------------------------------------------------
// Copyright The OpenMS Team -- Eberhard Karls University Tuebingen,
// ETH Zurich, and Freie Universitaet Berlin 2002-2024.
//
// This software is released under a three-clause BSD license.
// --------------------------------------------------------------------------
// Zero-copy Arrow export for pyOpenMS via nanobind
// --------------------------------------------------------------------------

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "arrow_table.h"
#include <OpenMS/KERNEL/MSExperiment.h>
#include <OpenMS/KERNEL/FeatureMap.h>
#include <OpenMS/KERNEL/ConsensusMap.h>
#include <OpenMS/METADATA/ProteinIdentification.h>
#include <OpenMS/FORMAT/MSExperimentArrowExport.h>
#include <OpenMS/FORMAT/FeatureMapArrowIO.h>
#include <OpenMS/FORMAT/ConsensusMapArrowIO.h>
#include <OpenMS/FORMAT/ProteinIdentificationArrowIO.h>


namespace nb = nanobind;
using PyOpenMS::ArrowGuard;
using PyOpenMS::import_to_pyarrow;
using PyOpenMS::table_to_pyarrow;
using PyOpenMS::pyarrow_to_table;

NB_MODULE(_arrow_zerocopy, m) {
    m.doc() = "Arrow conversion for OpenMS data.\n\n"
              "The C Data/Stream Interface transfers buffer ownership without copying. "
              "Scientific object conversion and combining output chunks may copy data. "
              "Imports accept tables or Arrow C stream providers and consume every batch.\n\n"
              ".. warning::\n"
              "    **EXPERIMENTAL API**: This module is experimental and may change.";

    m.def("spectra_to_arrow",
        [](nb::object exp_obj,
           std::string format,
           nb::object ms_levels_obj,
           double min_rt,
           double max_rt,
           double min_mz,
           double max_mz,
           nb::object columns_obj,
           bool include_precursor_info,
           bool include_ion_mobility) -> nb::object
        {
            // Cast to C++ reference via nanobind
            const auto& exp = nb::cast<const OpenMS::MSExperiment&>(exp_obj);

            // Build config
            OpenMS::ArrowSpectraExportConfig config;

            // Format
            std::string fmt = format;
            for (auto& c : fmt) c = static_cast<char>(std::tolower(c));
            if (fmt == "long")
                config.format = OpenMS::ArrowExportFormat::Long;
            else if (fmt == "semi_wide")
                config.format = OpenMS::ArrowExportFormat::SemiWide;
            else
                throw nb::value_error(("format must be 'long' or 'semi_wide', got '" + format + "'").c_str());

            config.min_rt = min_rt;
            config.max_rt = max_rt;
            config.min_mz = min_mz;
            config.max_mz = max_mz;
            config.include_precursor_info = include_precursor_info;
            config.include_ion_mobility = include_ion_mobility;

            // ms_levels
            if (!ms_levels_obj.is_none()) {
                for (auto item : ms_levels_obj) {
                    config.ms_levels.push_back(nb::cast<unsigned int>(item));
                }
            }

            // columns
            if (!columns_obj.is_none()) {
                for (auto item : columns_obj) {
                    config.columns.push_back(nb::cast<std::string>(item));
                }
            }

            // Allocate Arrow structs
            ArrowGuard guard;

            // Call C++ export (release GIL)
            bool success;
            {
                nb::gil_scoped_release release;
                success = OpenMS::MSExperimentArrowExport::exportSpectraToArrowCDataInterface(
                    exp, config, guard.schema, guard.array);
            }

            if (!success)
                throw std::runtime_error("Failed to export spectra to Arrow format");

            return import_to_pyarrow(guard);
        },
        nb::arg("exp"),
        nb::arg("format") = "long",
        nb::arg("ms_levels") = nb::none(),
        nb::arg("min_rt") = 0.0,
        nb::arg("max_rt") = 0.0,
        nb::arg("min_mz") = 0.0,
        nb::arg("max_mz") = 0.0,
        nb::arg("columns") = nb::none(),
        nb::arg("include_precursor_info") = true,
        nb::arg("include_ion_mobility") = true,
        "Export spectra to Arrow Table using zero-copy C Data Interface.\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );

    m.def("chromatograms_to_arrow",
        [](nb::object exp_obj,
           std::string format,
           double min_rt,
           double max_rt,
           nb::object columns_obj) -> nb::object
        {
            const auto& exp = nb::cast<const OpenMS::MSExperiment&>(exp_obj);

            OpenMS::ArrowChromatogramExportConfig config;

            std::string fmt = format;
            for (auto& c : fmt) c = static_cast<char>(std::tolower(c));
            if (fmt == "long")
                config.format = OpenMS::ArrowExportFormat::Long;
            else if (fmt == "semi_wide")
                config.format = OpenMS::ArrowExportFormat::SemiWide;
            else
                throw nb::value_error(("format must be 'long' or 'semi_wide', got '" + format + "'").c_str());

            config.min_rt = min_rt;
            config.max_rt = max_rt;

            if (!columns_obj.is_none()) {
                for (auto item : columns_obj) {
                    config.columns.push_back(nb::cast<std::string>(item));
                }
            }

            ArrowGuard guard;

            bool success;
            {
                nb::gil_scoped_release release;
                success = OpenMS::MSExperimentArrowExport::exportChromatogramsToArrowCDataInterface(
                    exp, config, guard.schema, guard.array);
            }

            if (!success)
                throw std::runtime_error("Failed to export chromatograms to Arrow format");

            return import_to_pyarrow(guard);
        },
        nb::arg("exp"),
        nb::arg("format") = "long",
        nb::arg("min_rt") = 0.0,
        nb::arg("max_rt") = 0.0,
        nb::arg("columns") = nb::none(),
        "Export chromatograms to Arrow Table using zero-copy C Data Interface.\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );

    // -----------------------------------------------------------------------
    // FeatureMapArrowIO — zero-copy Arrow export/import
    // -----------------------------------------------------------------------

    m.def("featuremap_features_to_arrow",
        [](nb::object fmap_obj) -> nb::object
        {
            const auto& fmap = nb::cast<const OpenMS::FeatureMap&>(fmap_obj);
            std::shared_ptr<arrow::Table> table;
            {
                nb::gil_scoped_release release;
                table = OpenMS::FeatureMapArrowIO::exportFeaturesToArrow(fmap);
            }
            return table_to_pyarrow(table);
        },
        nb::arg("feature_map"),
        "Export FeatureMap features to a PyArrow Table (via Arrow C Data Interface).\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );

    m.def("featuremap_psms_to_arrow",
        [](nb::object fmap_obj) -> nb::object
        {
            const auto& fmap = nb::cast<const OpenMS::FeatureMap&>(fmap_obj);
            std::shared_ptr<arrow::Table> table;
            {
                nb::gil_scoped_release release;
                table = OpenMS::FeatureMapArrowIO::exportPSMsToArrow(fmap);
            }
            return table_to_pyarrow(table);
        },
        nb::arg("feature_map"),
        "Export FeatureMap PSMs to a PyArrow Table (via Arrow C Data Interface).\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );

    m.def("featuremap_import_features_from_arrow",
        [](nb::object pa_table, nb::object fmap_obj) -> bool
        {
            auto& fmap = nb::cast<OpenMS::FeatureMap&>(fmap_obj);
            auto table = pyarrow_to_table(pa_table);
            nb::gil_scoped_release release;
            return OpenMS::FeatureMapArrowIO::importFeaturesFromArrow(table, fmap);
        },
        nb::arg("table"), nb::arg("feature_map"),
        "Import features from a PyArrow Table into a FeatureMap (via Arrow C Data Interface).\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );

    m.def("featuremap_import_psms_from_arrow",
        [](nb::object pa_table, nb::object fmap_obj) -> bool
        {
            auto& fmap = nb::cast<OpenMS::FeatureMap&>(fmap_obj);
            auto table = pyarrow_to_table(pa_table);
            nb::gil_scoped_release release;
            return OpenMS::FeatureMapArrowIO::importPSMsFromArrow(table, fmap);
        },
        nb::arg("table"), nb::arg("feature_map"),
        "Import PSMs from a PyArrow Table into a FeatureMap (via Arrow C Data Interface).\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );

    // -----------------------------------------------------------------------
    // ConsensusMapArrowIO — zero-copy Arrow export/import
    // -----------------------------------------------------------------------

    m.def("consensusmap_features_to_arrow",
        [](nb::object cmap_obj) -> nb::object
        {
            const auto& cmap = nb::cast<const OpenMS::ConsensusMap&>(cmap_obj);
            std::shared_ptr<arrow::Table> table;
            {
                nb::gil_scoped_release release;
                table = OpenMS::ConsensusMapArrowIO::exportFeaturesToArrow(cmap);
            }
            return table_to_pyarrow(table);
        },
        nb::arg("consensus_map"),
        "Export ConsensusMap features to a PyArrow Table (via Arrow C Data Interface).\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );

    m.def("consensusmap_psms_to_arrow",
        [](nb::object cmap_obj) -> nb::object
        {
            const auto& cmap = nb::cast<const OpenMS::ConsensusMap&>(cmap_obj);
            std::shared_ptr<arrow::Table> table;
            {
                nb::gil_scoped_release release;
                table = OpenMS::ConsensusMapArrowIO::exportPSMsToArrow(cmap);
            }
            return table_to_pyarrow(table);
        },
        nb::arg("consensus_map"),
        "Export ConsensusMap PSMs to a PyArrow Table (via Arrow C Data Interface).\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );

    m.def("consensusmap_import_features_from_arrow",
        [](nb::object pa_table, nb::object cmap_obj) -> bool
        {
            auto& cmap = nb::cast<OpenMS::ConsensusMap&>(cmap_obj);
            auto table = pyarrow_to_table(pa_table);
            nb::gil_scoped_release release;
            return OpenMS::ConsensusMapArrowIO::importFeaturesFromArrow(table, cmap);
        },
        nb::arg("table"), nb::arg("consensus_map"),
        "Import features from a PyArrow Table into a ConsensusMap (via Arrow C Data Interface).\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );

    m.def("consensusmap_import_psms_from_arrow",
        [](nb::object pa_table, nb::object cmap_obj) -> bool
        {
            auto& cmap = nb::cast<OpenMS::ConsensusMap&>(cmap_obj);
            auto table = pyarrow_to_table(pa_table);
            nb::gil_scoped_release release;
            return OpenMS::ConsensusMapArrowIO::importPSMsFromArrow(table, cmap);
        },
        nb::arg("table"), nb::arg("consensus_map"),
        "Import PSMs from a PyArrow Table into a ConsensusMap (via Arrow C Data Interface).\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );

    // -----------------------------------------------------------------------
    // ProteinIdentificationArrowIO — zero-copy Arrow export/import
    // -----------------------------------------------------------------------

    m.def("protein_ids_proteins_to_arrow",
        [](nb::object prot_ids_obj) -> nb::object
        {
            auto prot_ids = nb::cast<std::vector<OpenMS::ProteinIdentification>>(prot_ids_obj);
            std::shared_ptr<arrow::Table> table;
            {
                nb::gil_scoped_release release;
                table = OpenMS::ProteinIdentificationArrowIO::exportProteinsToArrow(prot_ids);
            }
            return table_to_pyarrow(table);
        },
        nb::arg("protein_identifications"),
        "Export protein hits to a PyArrow Table (via Arrow C Data Interface).\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );

    m.def("protein_ids_groups_to_arrow",
        [](nb::object prot_ids_obj) -> nb::object
        {
            auto prot_ids = nb::cast<std::vector<OpenMS::ProteinIdentification>>(prot_ids_obj);
            std::shared_ptr<arrow::Table> table;
            {
                nb::gil_scoped_release release;
                table = OpenMS::ProteinIdentificationArrowIO::exportProteinGroupsToArrow(prot_ids);
            }
            return table_to_pyarrow(table);
        },
        nb::arg("protein_identifications"),
        "Export protein groups to a PyArrow Table (via Arrow C Data Interface).\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );

    m.def("protein_ids_search_params_to_arrow",
        [](nb::object prot_ids_obj) -> nb::object
        {
            auto prot_ids = nb::cast<std::vector<OpenMS::ProteinIdentification>>(prot_ids_obj);
            std::shared_ptr<arrow::Table> table;
            {
                nb::gil_scoped_release release;
                table = OpenMS::ProteinIdentificationArrowIO::exportSearchParamsToArrow(prot_ids);
            }
            return table_to_pyarrow(table);
        },
        nb::arg("protein_identifications"),
        "Export search parameters to a PyArrow Table (via Arrow C Data Interface).\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );

    // Import methods: std::vector<ProteinIdentification>& is an output param.
    // Since vectors go through nanobind's STL type caster (creates copies),
    // we take by value, modify, and return the result.

    m.def("protein_ids_import_search_params_from_arrow",
        [](nb::object pa_table) -> std::vector<OpenMS::ProteinIdentification>
        {
            auto table = pyarrow_to_table(pa_table);
            std::vector<OpenMS::ProteinIdentification> prot_ids;
            bool ok;
            {
                nb::gil_scoped_release release;
                ok = OpenMS::ProteinIdentificationArrowIO::importSearchParamsFromArrow(table, prot_ids);
            }
            if (!ok) throw std::runtime_error("Failed to import search parameters from Arrow table");
            return prot_ids;
        },
        nb::arg("table"),
        "Import search parameters from a PyArrow Table. Returns list of ProteinIdentifications.\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );

    m.def("protein_ids_import_proteins_from_arrow",
        [](nb::object pa_table, std::vector<OpenMS::ProteinIdentification> prot_ids)
            -> std::vector<OpenMS::ProteinIdentification>
        {
            auto table = pyarrow_to_table(pa_table);
            bool ok;
            {
                nb::gil_scoped_release release;
                ok = OpenMS::ProteinIdentificationArrowIO::importProteinsFromArrow(table, prot_ids);
            }
            if (!ok) throw std::runtime_error("Failed to import proteins from Arrow table");
            return prot_ids;
        },
        nb::arg("table"), nb::arg("protein_identifications"),
        "Import protein hits from a PyArrow Table into existing ProteinIdentifications. Returns updated list.\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );

    m.def("protein_ids_import_groups_from_arrow",
        [](nb::object pa_table, std::vector<OpenMS::ProteinIdentification> prot_ids)
            -> std::vector<OpenMS::ProteinIdentification>
        {
            auto table = pyarrow_to_table(pa_table);
            bool ok;
            {
                nb::gil_scoped_release release;
                ok = OpenMS::ProteinIdentificationArrowIO::importProteinGroupsFromArrow(table, prot_ids);
            }
            if (!ok) throw std::runtime_error("Failed to import protein groups from Arrow table");
            return prot_ids;
        },
        nb::arg("table"), nb::arg("protein_identifications"),
        "Import protein groups from a PyArrow Table into existing ProteinIdentifications. Returns updated list.\n\n"
        ".. warning::\n"
        "    **EXPERIMENTAL API**: This function is experimental and may change."
    );
}
